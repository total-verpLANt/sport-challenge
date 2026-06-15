"""Tests für die gzip-komprimierte Log-Rotation (sport-challenge-8ag).

Beweist: Wenn der RotatingFileHandler mit _gzip_rotator/_gzip_namer rotiert,
entstehen .gz-Archive (statt unkomprimierter, verworfener Backups), die aktive
Logdatei bleibt unkomprimiert und der Archivinhalt ist verlustfrei lesbar.
"""

import gzip
import logging
from logging.handlers import RotatingFileHandler

from app import _gzip_namer, _gzip_rotator


def _make_handler(log_path):
    handler = RotatingFileHandler(
        log_path, maxBytes=1024, backupCount=3, encoding="utf-8"
    )
    handler.rotator = _gzip_rotator
    handler.namer = _gzip_namer
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def test_namer_appends_gz():
    assert _gzip_namer("access.log.1") == "access.log.1.gz"


def test_rotation_creates_gzip_archive(tmp_path):
    log_path = tmp_path / "access.log"
    logger = logging.getLogger("rotation_test_archive")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = _make_handler(str(log_path))
    logger.addHandler(handler)

    # Genug Zeilen, um mindestens eine Rotation (>1024 Bytes) auszulösen.
    for i in range(200):
        logger.info("logzeile-%03d-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", i)
    handler.close()

    archive = tmp_path / "access.log.1.gz"
    assert archive.exists(), "Rotiertes Log muss als .gz-Archiv vorliegen"
    # Aktive Logdatei bleibt unkomprimiert vorhanden.
    assert log_path.exists()
    # Es darf kein unkomprimiertes Backup übrig bleiben.
    assert not (tmp_path / "access.log.1").exists()

    # Archivinhalt ist valides gzip und enthält geloggte Zeilen.
    with gzip.open(archive, "rt", encoding="utf-8") as f:
        content = f.read()
    assert "logzeile-" in content


def test_rotation_respects_backup_count(tmp_path):
    log_path = tmp_path / "access.log"
    logger = logging.getLogger("rotation_test_backupcount")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = _make_handler(str(log_path))
    logger.addHandler(handler)

    for i in range(2000):
        logger.info("zeile-%04d-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", i)
    handler.close()

    # backupCount=3 → maximal 3 Archive (.1.gz .. .3.gz), nicht mehr.
    archives = sorted(tmp_path.glob("access.log.*.gz"))
    assert 1 <= len(archives) <= 3
    for archive in archives:
        # Jedes Archiv muss dekomprimierbar sein (kein korruptes gzip).
        with gzip.open(archive, "rt", encoding="utf-8") as f:
            assert "zeile-" in f.read()
