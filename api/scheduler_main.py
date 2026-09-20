import signal
import threading

from api.logging_config import configure_logging
from api.scheduler_service import shutdown_scheduler, start_scheduler


def main():
    configure_logging()
    stopped = threading.Event()

    def stop(*_):
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    start_scheduler(run_workers=False)
    stopped.wait()
    shutdown_scheduler()


if __name__ == "__main__":
    main()
