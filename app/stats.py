import math


def two_proportion_z_test(conversions_a: int, n_a: int, conversions_b: int, n_b: int):
    """
    Two-proportion z-test comparing conversion rates between variant A (control)
    and variant B (treatment). Returns (z_score, p_value).
    Uses the normal approximation with a pooled standard error.
    """
    if n_a == 0 or n_b == 0:
        return None, None

    p_a = conversions_a / n_a
    p_b = conversions_b / n_b
    p_pool = (conversions_a + conversions_b) / (n_a + n_b)

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    if se == 0:
        return None, None

    z = (p_b - p_a) / se
    # two-tailed p-value from the standard normal CDF
    p_value = 2 * (1 - _standard_normal_cdf(abs(z)))
    return z, p_value


def _standard_normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
