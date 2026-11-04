"""Hosted entry point for the public dashboard and its approved data snapshot."""

import logging
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import BadZipFile

import streamlit as st

repository = str(Path(__file__).resolve().parents[1])
if repository not in sys.path:
    sys.path.insert(0, repository)

from app.streamlit_app import main
from src.public_dashboard_data import RELEASE_URL, unpack_bundle


BUNDLE_SHA256 = "130226221ebc30c823c60827fa4bff4dc9aa9085a2cc8e074ecda3f0defa2006"
LOGGER = logging.getLogger(__name__)


@st.cache_resource
def prepare_public_data():
    with urlopen(RELEASE_URL, timeout=30) as response:
        payload = response.read()
    if sha256(payload).hexdigest() != BUNDLE_SHA256:
        raise ValueError("The public data archive differs from the approved snapshot.")

    directory = TemporaryDirectory(prefix="malaria-dashboard-public-")
    try:
        unpack_bundle(payload, Path(directory.name))
    except (OSError, ValueError, BadZipFile):
        directory.cleanup()
        raise
    return directory


if __name__ == "__main__":
    try:
        data = prepare_public_data()
    except (OSError, ValueError, BadZipFile):
        LOGGER.exception("Could not load the published dashboard data")
        st.error("The public dashboard data is temporarily unavailable.")
        st.stop()
    main(data_dir=Path(data.name))
