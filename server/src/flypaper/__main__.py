import logging

from . import config, pollers
from .app import make_server
from .guestbook import Guestbook


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.PUBLIC_DIR.is_dir():
        raise SystemExit(f"Папка сайта не найдена: {config.PUBLIC_DIR} (задайте FLYPAPER_PUBLIC_DIR)")

    state = pollers.State()
    pollers.start(state)
    server = make_server(config.HOST, config.PORT, state, config.PUBLIC_DIR, Guestbook(config.GUESTBOOK_FILE))
    logging.getLogger("flypaper").info("Flypaper: http://%s:%s (сайт: %s)", config.HOST, config.PORT, config.PUBLIC_DIR)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
