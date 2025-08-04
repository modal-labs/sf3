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

from omegaconf import OmegaConf, open_dict
from verl.single_controller.base.decorator import Dispatch, register
from verl.utils.import_utils import import_external_libs
from verl.workers.fsdp_workers import ActorRolloutRefWorker

from .dp_actor import DataParallelSPPOActor

logger = logging.getLogger(__file__)
logger.setLevel(os.getenv("VERL_PPO_LOGGING_LEVEL", "WARN"))


class SPPOActorRolloutRefWorker(ActorRolloutRefWorker):
    """SPPO version of ActorRolloutRefWorker that uses DataParallelSPPOActor"""

    @register(dispatch_mode=Dispatch.ONE_TO_ALL)
    def init_model(self):
        """Initialize models with SPPO actor"""
        # Import external libs
        import_external_libs(self.config.model.get("external_lib", None))

        # Call parent initialization
        super().init_model()

        # Replace the actor with SPPO version if we're an actor
        if self._is_actor:
            # Ensure sppo_eta is in actor config
            OmegaConf.set_struct(self.config.actor, True)
            with open_dict(self.config.actor):
                if "sppo_eta" not in self.config.actor:
                    self.config.actor.sppo_eta = self.config.algorithm.get(
                        "sppo_eta", 1.0
                    )

            # Create SPPO actor
            self.actor = DataParallelSPPOActor(
                config=self.config.actor,
                actor_module=self.actor_module_fsdp,
                actor_optimizer=self.actor_optimizer,
            )

        # For reference policy, also use SPPO actor (though it only computes log probs)
        if self._is_ref:
            OmegaConf.set_struct(self.config.ref, True)
            with open_dict(self.config.ref):
                self.config.ref.sppo_eta = self.config.algorithm.get("sppo_eta", 1.0)

            self.ref_policy = DataParallelSPPOActor(
                config=self.config.ref, actor_module=self.ref_module_fsdp
            )

    def get_metric(self, metric_name):
        """Get specific metrics from the worker"""
        if metric_name == "mfu" and hasattr(self, "flops_counter"):
            # Calculate MFU if we have a flops counter
            try:
                mfu_value = self.flops_counter.get_mfu()
                return {"mfu/actor": mfu_value}
            except Exception:
                pass
        return {}
