"""
config.py: Training hyperparameters and configuration dataclass for SR-EdgeNet.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class SREdgeNetConfig:
    """Hyperparameter configuration for Spatial-Relational Edge Classifier."""

    # Model architecture parameters
    input_dim: int = 15                  # 15-dimensional spatial feature vector
    hidden_dims: Tuple[int, ...] = (256, 128, 64)
    num_classes: int = 4                 # PARENT_OF, OPTION_OF, CONTINUATION_OF, NONE
    dropout_rate: float = 0.20
    activation: str = "relu"             # 'relu', 'gelu', 'leaky_relu'
    use_batch_norm: bool = True

    # Training optimization
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 30
    early_stopping_patience: int = 5
    lr_scheduler_factor: float = 0.50
    lr_scheduler_patience: int = 2

    # Class weighting & loss configuration
    loss_function: str = "focal"         # 'cross_entropy', 'focal'
    focal_gamma: float = 2.0
    # Class weights for [PARENT_OF, OPTION_OF, CONTINUATION_OF, NONE]
    class_weights: List[float] = field(default_factory=lambda: [1.2, 1.0, 1.5, 0.4])

    # Hardware & reproducibility
    device: str = "cpu"                  # Target laptop execution
    num_workers: int = 0                 # Windows multiprocessing compatibility
    seed: int = 42

    # Target class mappings
    label_to_id: dict = field(default_factory=lambda: {
        "PARENT_OF": 0,
        "OPTION_OF": 1,
        "CONTINUATION_OF": 2,
        "NONE": 3
    })
    id_to_label: dict = field(default_factory=lambda: {
        0: "PARENT_OF",
        1: "OPTION_OF",
        2: "CONTINUATION_OF",
        3: "NONE"
    })
