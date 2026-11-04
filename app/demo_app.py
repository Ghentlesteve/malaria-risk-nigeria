"""Public Streamlit entry point for the synthetic dashboard."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

# The Streamlit launcher adds the entry point directory to the import path.
repository = str(Path(__file__).resolve().parents[1])
if repository not in sys.path:
    sys.path.insert(0, repository)

from app.streamlit_app import main
from src.demo_data import generate_demo


@st.cache_resource
def prepare_demo():
    directory = TemporaryDirectory(prefix="malaria-dashboard-demo-")
    generate_demo(Path(directory.name))
    return directory


if __name__ == "__main__":
    main(demo_dir=Path(prepare_demo().name))
