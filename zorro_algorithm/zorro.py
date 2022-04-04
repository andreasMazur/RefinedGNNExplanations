from zorro_algorithm.discrete_mask import DiscreteMask
from zorro_algorithm.zorro_utils import get_best_explanation

import tensorflow as tf
import numpy as np
import sys


def get_explanations(V_p, F_p, threshold_fidelity, X, A, gnn, verbose=True):

    S = []
    mask = DiscreteMask(V_p, F_p)

    # Determine first element in the explanation from the selectable nodes or features
    remaining_elems_left = mask.init_mask(X, A, gnn)

    # Add new elements to the mask as long as the fidelity remains
    # "good enough", which is determined by the target fidelity.
    mask_fidelity = mask.compute_mask_fidelity(X, A, gnn)

    # As long as we produce a fidelity that is smaller than our threshold fidelity,
    # we add more values to the mask such that more original values retain their
    # values.
    loading_signs = ["-", "\\", "|", "/"]
    idx = -1
    while mask_fidelity < threshold_fidelity and remaining_elems_left:  # (IV)
        if verbose:
            sys.stdout.write(
                f"\rZORRO::: "
                f"Current mask V_s: {mask.V_s} F_s: {mask.F_s} - "
                f"Remaining V_r: {mask.V_r} F_r: {mask.F_r} - "
                f"Mask fidelity: {mask_fidelity:.3f}"
            )
        else:
            loading_sign = loading_signs[idx]
            idx = (idx + 1) % 4
            sys.stdout.write(f"\rZorro algorithm is working. {loading_sign}")
        R_Vr, R_Fr = mask.compute_current_ranking(X, A, gnn)
        remaining_elems_left = mask.add_element_to_mask(R_Vr, R_Fr)
        mask_fidelity = mask.compute_mask_fidelity(X, A, gnn)
    '''
    +-------------------------------------+--------------------------------------------------------+
    |  mask_fidelity < threshold_fidelity | remaining_elems_left                                   |
    | ------------------------------------+--------------------------------------------------------|
    |                 0                   |       0           : Return mask, no recursion     (I)  |
    |                 0                   |       1           : Return mask, recursion        (II) |
    |                 1                   |       0           : Return mask, no recursion     (III)|
    |                 1                   |       1           : While loop                    (IV) |
    +----------------------------------------------------------------------------------------------+
    '''
    if mask_fidelity >= threshold_fidelity and not remaining_elems_left:  # (I)
        return [(mask.V_p, mask.F_p, mask_fidelity)]
    elif mask_fidelity <= threshold_fidelity and not remaining_elems_left:  # (III)
        # Instead of no mask we return the best possible mask if threshold fidelity wasn't
        # exceeded.
        return [(mask.best_V_p, mask.best_F_p, mask.best_fidelity)]
    else:  # (II)
        explanation = [(mask.V_s, mask.F_s, mask_fidelity)]
        S.extend(explanation)
        S.extend(get_explanations(mask.V_p, mask.F_r, threshold_fidelity, X, A, gnn))
        S.extend(get_explanations(mask.V_r, mask.F_p, threshold_fidelity, X, A, gnn))

    return S


def zorro(gnn, X, A, threshold_fidelity=.9):
    """The entry point for the Zorro algorithm.

    :param gnn: The graph neural network to explain.
    :param X: The original feature matrix for which an explanation shall be computed.
    :param A: The corresponding adjacency matrix.
    :param threshold_fidelity: A minimum fidelity to be reached
    :return: Multiple possible explanations for a given observation.
    """

    if len(X.shape) == 2:
        X = tf.expand_dims(X, axis=0)

    shape = X.shape
    V_p = set(np.arange(shape[1]))
    F_p = set(np.arange(shape[2]))

    return get_explanations(V_p, F_p, threshold_fidelity, X, A, gnn)


def zorro_wrapper(gnn, X, A, target_action, threshold_fidelity=.9):
    """Returns the best explanation from the zorro algorithm

    :param gnn: The graph neural network to explain.
    :param X: The original feature matrix for which an explanation shall be computed.
    :param A: The corresponding adjacency matrix.
    :param target_action: The action predicted on the original input.
    :param threshold_fidelity: A minimum fidelity to be reached.
    :return: The best explanation that Zorro has found for a given observation and target action.
    """

    explanations = zorro(gnn, X, A, threshold_fidelity)
    explanation, action, q_values = get_best_explanation(explanations, gnn, X, target_action)

    return explanation, action, q_values
