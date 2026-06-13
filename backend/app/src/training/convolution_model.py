import numpy as np
import tensorflow as tf
from keras import layers, Model


def build_unet(
    input_channels: int,        # Number of features
    patch_size: int = 64,
    base_filters: int = 64,
) -> Model:
    if patch_size % 8 != 0:
        raise ValueError(
            f"patch_size must be divisible by 8 (3 pooling stages)"
        )