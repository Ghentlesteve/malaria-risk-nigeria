"""Hosted entry point for the public dashboard and its approved data snapshot."""

import logging
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import urlopen
from zipfile import BadZipFile

import streamlit as st

repository = str(Path(__file__).resolve().parents[1])
if repository not in sys.path:
    sys.path.insert(0, repository)

from app.streamlit_app import main
from src.public_dashboard_data import FORECAST_MEMBERS, FORECAST_RELEASE_URL, MEMBERS, RELEASE_URL, unpack_bundle


BUNDLE_SHA256 = "130226221ebc30c823c60827fa4bff4dc9aa9085a2cc8e074ecda3f0defa2006"
FORECAST_SHA256 = "4e7795feb407378516926c6f13b446c67812166bb77e0861ce63969464806803"
LOGGER = logging.getLogger(__name__)


def download_bundle(url, checksum, members, timeout):
    with urlopen(url, timeout=timeout) as response:
        payload = response.read()
    if sha256(payload).hexdigest() != checksum:
        raise ValueError("The public data archive differs from the approved snapshot.")

    directory = TemporaryDirectory(prefix="malaria-dashboard-public-")
    try:
        unpack_bundle(payload, Path(directory.name), members)
    except (OSError, ValueError, BadZipFile):
        directory.cleanup()
        raise
    return directory


@st.cache_resource
def prepare_public_data():
    return download_bundle(RELEASE_URL, BUNDLE_SHA256, MEMBERS, timeout=30)


@st.cache_resource(ttl=300)
def prepare_public_forecast():
    try:
        return download_bundle(FORECAST_RELEASE_URL, FORECAST_SHA256, FORECAST_MEMBERS, timeout=10)
    except (OSError, ValueError, BadZipFile) as error:
        if not isinstance(error, HTTPError) or error.code != 404:
            LOGGER.exception("Could not load the published forecast trial")
        return None


if __name__ == "__main__":
    try:
        data = prepare_public_data()
    except (OSError, ValueError, BadZipFile):
        LOGGER.exception("Could not load the published dashboard data")
        st.error("The public dashboard data is temporarily unavailable.")
        st.stop()
    forecast = prepare_public_forecast()
    main(data_dir=Path(data.name), forecast_dir=Path(forecast.name) if forecast is not None else None)
