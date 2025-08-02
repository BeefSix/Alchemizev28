import logging
import sys

# --- Logger Configuration ---

# Define the format for our log messages
log_format = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create a logger instance
logger = logging.getLogger("alchemize")
logger.setLevel(logging.INFO)

# Create a handler to print log messages to the console (standard output)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_format)

# Add the handler to our logger
logger.addHandler(stream_handler)

# --- End Configuration ---

logger.info("Logger initialized")