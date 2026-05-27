# All tunable parameters in one place.
# Do not hardcode any of these values elsewhere.

NUM_BINS = 8          # Histogram bins per channel (8^3 = 512 total bins)
EPSILON = 1e-6        # Added to every histogram bin before log to prevent log(0)
BLUR_SIGMA = 1.0      # Gaussian blur sigma for preprocessing (0 = disabled)
CONNECTIVITY = 8      # Neighbourhood connectivity: 4 or 8
