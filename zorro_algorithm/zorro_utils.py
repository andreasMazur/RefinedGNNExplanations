from double_q_learning.neural_networks import load_agent
from double_q_learning.preprocessing import AMT_NODES, FEATURE_DIM, ADJ_MATRIX_SPARSE

import tensorflow as tf
import numpy as np


def get_best_explanation(masks, model_, X, target_action):
    """Choose the best mask from all given masks."""
    chosen_mask, action, q_values = None, None, None
    best_fidelity = -np.inf
    best_fidelity_has_correct_action = False
    for (V_s, F_s, mask_fidelity) in masks:

        mask = create_mask(V_s, F_s)
        explanation = X * mask

        if len(X.shape) == 2:
            explanation = tf.expand_dims(explanation, axis=0)
        explanation = tf.cast(explanation, tf.float32)
        q_values, _ = model_((explanation, ADJ_MATRIX_SPARSE))
        q_values = q_values[0]
        action = np.argmax(q_values)

        if mask_fidelity > best_fidelity and best_fidelity_has_correct_action:
            if action == target_action:
                best_fidelity_has_correct_action = True
                best_fidelity = mask_fidelity
                chosen_mask = explanation
        elif mask_fidelity > best_fidelity:
            best_fidelity = mask_fidelity
            chosen_mask = explanation

    # best_fidelity = -np.inf
    # chosen_mask = None
    # for (V_s, F_s, mask_fidelity) in masks:
    #     if mask_fidelity > best_fidelity:
    #         chosen_mask = (V_s, F_s)

    assert chosen_mask is not None, "No masks given!"
    assert action is not None, "No masks given!"
    assert q_values is not None, "No masks given!"

    return chosen_mask, action, q_values


def create_mask(V_s, F_s):
    """Create the actual mask given a Zorro explanation."""

    mask = np.zeros((AMT_NODES, FEATURE_DIM), dtype=np.int32)
    for node in V_s:
        for feature in F_s:
            mask[node, feature] = 1
    return mask


def compute_fidelity(gnn, X, A, V_s, F_s, samples=250):
    """Computes the fidelity."""

    # Original prediction for X
    q_values, _ = gnn((X, A))
    q_values = q_values[0]
    action = np.argmax(q_values)

    # Noisy input memory
    noisy_input_mem = []

    # Create mask
    mask = create_mask(V_s, F_s)
    masked_features = mask * X

    for _ in range(samples):

        # Create random values
        negated_mask = np.logical_not(mask).astype(np.int32)
        random_values = np.random.uniform(size=(AMT_NODES, FEATURE_DIM))

        # Modify input
        modified_input = masked_features + (negated_mask * random_values)
        noisy_input_mem.append(modified_input)

    noisy_input_mem = np.concatenate(noisy_input_mem, axis=0)

    # Noisy prediction
    noisy_q_values, _ = gnn((noisy_input_mem, A))
    noisy_actions = np.argmax(noisy_q_values, axis=-1)

    # Comparison
    comparison = (action == noisy_actions).astype(np.int32)
    fidelity = np.sum(comparison) / samples

    return fidelity


def compute_fidelity_2(gnn, X, A, V_s, F_s, samples=250):
    """Computes the fidelity."""

    # Original prediction for X
    q_values, _ = gnn((X, A))
    q_values = q_values[0]

    # Noisy input memory
    noisy_input_mem = []

    # Create mask
    mask = create_mask(V_s, F_s)
    masked_features = mask * X

    for _ in range(samples):

        # Create random values
        negated_mask = np.logical_not(mask).astype(np.int32)
        random_values = np.random.uniform(size=(AMT_NODES, FEATURE_DIM))

        # Modify input
        modified_input = masked_features + (negated_mask * random_values)
        noisy_input_mem.append(modified_input)

    noisy_input_mem = np.concatenate(noisy_input_mem, axis=0)

    # Noisy prediction
    noisy_q_values, _ = gnn((noisy_input_mem, A))

    # Comparison
    comparison = mean_squared_error(q_values, noisy_q_values)
    fidelity = -np.mean(comparison)

    return fidelity


def compute_fidelity_alternative(gnn, X, A, V_s, F_s):
    """Computes the fidelity."""

    # Original prediction for X
    q_values, _ = gnn((X, A))
    q_values = q_values[0]

    mask = create_mask(V_s, F_s)
    explanation = X * mask

    # Noisy prediction
    noisy_q_values, _ = gnn((explanation, A))
    noisy_q_values = noisy_q_values[0]

    # Comparison
    comparison = mean_squared_error(q_values, noisy_q_values)
    fidelity = -np.mean(comparison)

    return fidelity


def new_feature_fidelity(feature, V_s, F_s, gnn, X, A):
    F_s = np.concatenate([np.array([feature]), F_s])
    return compute_fidelity(gnn, X, A, V_s, F_s)


def new_node_fidelity(node, V_s, F_s, gnn, X, A):
    V_s = np.concatenate([np.array([node]), V_s])
    return compute_fidelity(gnn, X, A, V_s, F_s)


def mean_squared_error(q_original, q_noisy):
    """Mean squared error to compute fidelity

    Computes q-value-vector-wise difference, squares the difference
    and computes the mean deviation between two q-value vectors.

    Lastly it means over all mean-differences if multiple vector-pairs
    are given.

    :param q_original: Original q-values
    :param q_noisy: Q-values given by a prediction of an explanation
    :return: Mean squared error
    """

    return np.square(q_original - q_noisy).mean(axis=-1).mean()


if __name__ == "__main__":
    # Load the agent
    h_set = {
        "learning_rate": [.001],
        "batch_size": [64],
        "graph_layers": [64],  # depends on what model you retrain
        "expl_graph_layers": [128],
        "fidelity_reg": [.001]
    }
    model = load_agent("../double_q_learning/checkpoints/rl_agent_4", h_set)
    model.load_weights(
        "../learn_explanations/checkpoints/transfer_learning_no_rounding_2/test_set_0"
    )
    X_ = np.random.normal(size=(1, AMT_NODES, FEATURE_DIM))
    V_s_, F_s_ = {1, 2, 3}, {2}
    V_p_, F_p_ = set(np.arange(AMT_NODES)), set(np.arange(FEATURE_DIM))

    ############################
    # Test fidelity computation
    ############################
    fid_1 = compute_fidelity(model, X_, ADJ_MATRIX_SPARSE, V_s_, F_s_)
    fid_2 = compute_fidelity(model, X_, ADJ_MATRIX_SPARSE, V_p_, F_p_)

    print(f"fid_selected: {fid_1}; fid_all: {fid_2}")
