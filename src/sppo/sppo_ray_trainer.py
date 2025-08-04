# Copyright 2024 Bytedance Ltd. and/or its affiliates
# Copyright 2023-2024 SGLang Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Simplified SPPO Trainer with Ray-based single controller.
"""

import uuid
from pprint import pprint

import numpy as np
import torch
from tqdm import tqdm
from verl import DataProto
from verl.trainer.ppo.ray_trainer import (
    RayPPOTrainer,
    apply_kl_penalty,
    compute_response_mask,
)
from verl.trainer.ppo.reward import compute_reward
from verl.utils.metric import reduce_metrics
from verl.utils.profiler.performance import simple_timer


def softmean(x: torch.Tensor, beta: float) -> torch.Tensor:
    """
    Compute SoftMean_β(x) = (1/β) * log( (1/n) * Σ exp(β * x_i) )
    """
    if beta == 0.0:
        return x.mean()
    lse = torch.logsumexp(x * beta, dim=0)
    n = x.size(0)
    return (lse - torch.log(torch.tensor(n, dtype=x.dtype))) / beta


def compute_advantage(data: DataProto, beta: float = 1.0):
    """Compute SPPO advantages using SoftMean"""
    rewards = data.batch["token_level_rewards"].sum(axis=-1)  # (bs,)
    s_mean = softmean(rewards, beta)
    data.batch["seq_level_rewards"] = rewards - s_mean
    return data


class RaySPPOTrainer(RayPPOTrainer):
    """Simplified SPPO Trainer without critic"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SPPO doesn't use critic
        self.use_critic = False

    def fit(self):
        """Simplified training loop for SPPO"""
        from omegaconf import OmegaConf
        from verl.utils.tracking import Tracking

        logger = Tracking(
            project_name=self.config.trainer.project_name,
            experiment_name=self.config.trainer.experiment_name,
            default_backend=self.config.trainer.logger,
            config=OmegaConf.to_container(self.config, resolve=True),
        )

        self.global_steps = 0
        self._load_checkpoint()

        # Validation before training
        if self.val_reward_fn and self.config.trainer.get("val_before_train", True):
            val_metrics = self._validate()
            pprint(f"Initial validation metrics: {val_metrics}")
            logger.log(data=val_metrics, step=self.global_steps)
            if self.config.trainer.get("val_only", False):
                return

        progress_bar = tqdm(
            total=self.total_training_steps,
            initial=self.global_steps,
            desc="SPPO Training",
        )

        self.global_steps += 1

        for epoch in range(self.config.trainer.total_epochs):
            metrics = {}
            is_last_step = False

            for batch_dict in self.train_dataloader:
                timing = {}
                batch: DataProto = DataProto.from_single_dict(batch_dict)

                # Prepare generation batch
                gen_batch = batch.pop(
                    batch_keys=["input_ids", "attention_mask", "position_ids"],
                    non_tensor_batch_keys=["raw_prompt_ids"],
                )
                gen_batch = gen_batch.repeat(
                    repeat_times=self.config.actor_rollout_ref.rollout.n,
                    interleave=True,
                )

                is_last_step = self.global_steps >= self.total_training_steps

                with simple_timer("step", timing):
                    # Generate responses
                    with simple_timer("gen", timing):
                        gen_output = self.actor_rollout_wg.generate_sequences(gen_batch)
                        timing.update(gen_output.meta_info.get("timing", {}))

                    batch.non_tensor_batch["uid"] = np.array(
                        [str(uuid.uuid4()) for _ in range(len(batch.batch))],
                        dtype=object,
                    )
                    batch = batch.repeat(
                        repeat_times=self.config.actor_rollout_ref.rollout.n,
                        interleave=True,
                    )
                    batch = batch.union(gen_output)
                    batch.batch["response_mask"] = compute_response_mask(batch)

                    # Add global token count for compatibility
                    batch.meta_info["global_token_num"] = torch.sum(
                        batch.batch["attention_mask"], dim=-1
                    ).tolist()

                    # Compute rewards
                    with simple_timer("reward", timing):
                        if self.use_rm:
                            reward_tensor = self.rm_wg.compute_rm_score(batch)
                            batch = batch.union(reward_tensor)

                        reward_tensor, reward_info = compute_reward(
                            batch, self.reward_fn
                        )
                        batch.batch["token_level_scores"] = reward_tensor

                    # Compute old log probs
                    with simple_timer("old_log_prob", timing):
                        old_log_prob = self.actor_rollout_wg.compute_log_prob(batch)
                        batch = batch.union(old_log_prob)

                    # Reference policy log probs if using KL penalty
                    if self.use_reference_policy:
                        with simple_timer("ref", timing):
                            ref_log_prob = self.ref_policy_wg.compute_ref_log_prob(
                                batch
                            )
                            batch = batch.union(ref_log_prob)

                    # Apply KL penalty if configured
                    with simple_timer("adv", timing):
                        if self.config.algorithm.use_kl_in_reward:
                            batch, kl_metrics = apply_kl_penalty(
                                batch,
                                kl_ctrl=self.kl_ctrl_in_reward,
                                kl_penalty=self.config.algorithm.kl_penalty,
                            )
                            metrics.update(kl_metrics)
                        else:
                            batch.batch["token_level_rewards"] = batch.batch[
                                "token_level_scores"
                            ]

                        # Compute SPPO advantages
                        beta = self.config.algorithm.sppo_eta
                        batch = compute_advantage(batch, beta=beta)

                        # Add reward statistics
                        rewards = batch.batch["token_level_rewards"].sum(dim=-1)
                        metrics["rewards/mean"] = rewards.mean().item()
                        metrics["rewards/std"] = rewards.std().item()
                        metrics["rewards/max"] = rewards.max().item()
                        metrics["rewards/min"] = rewards.min().item()

                    # Update actor
                    with simple_timer("update_actor", timing):
                        actor_output = self.actor_rollout_wg.update_actor(batch)
                        actor_metrics = reduce_metrics(
                            actor_output.meta_info["metrics"]
                        )
                        metrics.update(actor_metrics)

                # Validation
                if (
                    self.val_reward_fn
                    and self.config.trainer.test_freq > 0
                    and (
                        is_last_step
                        or self.global_steps % self.config.trainer.test_freq == 0
                    )
                ):
                    with simple_timer("testing", timing):
                        val_metrics = self._validate()
                        metrics.update(val_metrics)

                # Checkpointing
                if self.config.trainer.save_freq > 0 and (
                    is_last_step
                    or self.global_steps % self.config.trainer.save_freq == 0
                ):
                    with simple_timer("save_checkpoint", timing):
                        self._save_checkpoint()

                # Log metrics
                metrics.update(
                    {
                        "training/global_step": self.global_steps,
                        "training/epoch": epoch,
                    }
                )

                # Add sequence length metrics
                if "attention_mask" in batch.batch:
                    seq_lengths = batch.batch["attention_mask"].sum(dim=-1)
                    metrics["global_seqlen/mean"] = seq_lengths.float().mean().item()
                    metrics["global_seqlen/max"] = seq_lengths.max().item()
                    metrics["global_seqlen/min"] = seq_lengths.min().item()
                    metrics["global_seqlen/minmax_diff"] = (
                        metrics["global_seqlen/max"] - metrics["global_seqlen/min"]
                    )

                    # Balanced min/max are per-rank min/max for distributed training
                    # In single-rank case, they're the same as regular min/max
                    metrics["global_seqlen/balanced_min"] = metrics["global_seqlen/min"]
                    metrics["global_seqlen/balanced_max"] = metrics["global_seqlen/max"]

                # Add timing metrics
                for key, value in timing.items():
                    metrics[f"perf/{key}_time"] = value

                # Add memory metrics
                if torch.cuda.is_available():
                    metrics["perf/max_memory_allocated_gb"] = (
                        torch.cuda.max_memory_allocated() / 1e9
                    )
                    metrics["perf/max_memory_reserved_gb"] = (
                        torch.cuda.max_memory_reserved() / 1e9
                    )
                    torch.cuda.reset_peak_memory_stats()

                # CPU memory
                try:
                    import psutil

                    process = psutil.Process()
                    metrics["perf/cpu_memory_used_gb"] = process.memory_info().rss / 1e9
                except ImportError:
                    pass

                # MFU calculation would require flops counter from the worker
                # Request it from actor if available
                if hasattr(self, "actor_rollout_wg"):
                    try:
                        mfu_metrics = self.actor_rollout_wg.get_metric("mfu")
                        if mfu_metrics and "mfu/actor" in mfu_metrics:
                            metrics["perf/mfu/actor"] = mfu_metrics["mfu/actor"]
                    except Exception:
                        pass

                logger.log(data=metrics, step=self.global_steps)

                if is_last_step:
                    progress_bar.close()
                    return

                progress_bar.update(1)
                self.global_steps += 1
