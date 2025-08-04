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

import logging
import os

from verl import DataProto
from verl.utils.device import get_device_id
from verl.utils.py_functional import append_to_dict
from verl.workers.actor.dp_actor import DataParallelPPOActor

logger = logging.getLogger(__file__)
logger.setLevel(os.getenv("VERL_LOGGING_LEVEL", "WARN"))


class DataParallelSPPOActor(DataParallelPPOActor):
    """Simplified SPPO Actor that only overrides the loss computation"""

    def compute_sppo_loss(self, log_prob, old_log_prob, rewards, response_mask):
        """
        SPPO Loss: L = (log_ratio - eta * rewards)^2
        """
        # Compute log-ratios
        log_prob_sum = (log_prob * response_mask).sum(dim=1)
        old_log_prob_sum = (old_log_prob * response_mask).sum(dim=1)
        log_ratios = log_prob_sum - old_log_prob_sum

        # Scale rewards by eta
        eta = self.config.get("sppo_eta", 1.0)
        scaled_rewards = eta * rewards

        # Squared loss
        loss_vec = (log_ratios - scaled_rewards) ** 2

        # Average over valid samples
        sample_mask = response_mask.any(dim=1).float()
        loss = (loss_vec * sample_mask).sum() / sample_mask.sum()

        return loss, log_ratios, scaled_rewards

    def update_policy(self, data: DataProto):
        """Simplified update for SPPO"""
        self.actor_module.train()

        temperature = data.meta_info["temperature"]

        # Prepare data
        select_keys = [
            "responses",
            "input_ids",
            "attention_mask",
            "position_ids",
            "old_log_probs",
            "seq_level_rewards",
        ]
        batch = data.select(batch_keys=select_keys).batch

        # Create mini-batches
        dataloader = batch.split(self.config.ppo_mini_batch_size)

        metrics = {}
        for epoch in range(self.config.ppo_epochs):
            for mini_batch in dataloader:
                # Split into micro-batches
                micro_batches = mini_batch.split(
                    self.config.ppo_micro_batch_size_per_gpu
                )
                self.gradient_accumulation = len(micro_batches)

                self.actor_optimizer.zero_grad()

                for micro_batch in micro_batches:
                    # Move to device
                    micro_batch = micro_batch.to(get_device_id())

                    # Extract data
                    responses = micro_batch["responses"]
                    response_length = responses.size(1)
                    attention_mask = micro_batch["attention_mask"]
                    response_mask = attention_mask[:, -response_length:]

                    old_log_prob = micro_batch["old_log_probs"]
                    rewards = micro_batch["seq_level_rewards"]

                    # Forward pass
                    entropy, log_prob = self._forward_micro_batch(
                        micro_batch=micro_batch,
                        temperature=temperature,
                        calculate_entropy=self.config.entropy_coeff != 0,
                    )

                    # Compute SPPO loss
                    loss, log_ratios, scaled_rewards = self.compute_sppo_loss(
                        log_prob, old_log_prob, rewards, response_mask
                    )

                    # Add entropy regularization if needed
                    if self.config.entropy_coeff != 0:
                        entropy_loss = (
                            -(entropy * response_mask).sum() / response_mask.sum()
                        )
                        loss = loss - self.config.entropy_coeff * entropy_loss
                        metrics["actor/entropy"] = entropy_loss.detach().item()

                    # Scale loss for gradient accumulation
                    loss = loss / self.gradient_accumulation
                    loss.backward()

                    # Collect metrics
                    batch_metrics = {
                        "actor/loss": loss.detach().item() * self.gradient_accumulation,
                        "actor/pg_loss": loss.detach().item()
                        * self.gradient_accumulation,  # SPPO loss is the PG loss
                        "actor/log_ratio_mean": log_ratios.mean().detach().item(),
                        "actor/preference_mean": scaled_rewards.mean().detach().item(),
                    }
                    append_to_dict(metrics, batch_metrics)

                # Optimizer step
                grad_norm = self._optimizer_step()
                metrics["actor/grad_norm"] = grad_norm.detach().item()

                # Add learning rate
                if hasattr(self.actor_optimizer, "param_groups"):
                    metrics["actor/lr"] = self.actor_optimizer.param_groups[0]["lr"]

        self.actor_optimizer.zero_grad()
        return metrics
