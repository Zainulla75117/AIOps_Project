"""Shared test fixtures."""

import os

import pytest

# Ensure config doesn't require a real Gemini key during tests
os.environ.setdefault("AIOPS_GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("AIOPS_K8S_IN_CLUSTER", "false")
