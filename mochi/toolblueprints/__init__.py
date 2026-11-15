"""Vetted blueprints used by the Tool Creation Agent in offline mode.

A blueprint is a complete, validated tool implementation.  It is copied into
``tools_created/`` (so the run has a real artefact on disk), imported, and its
``validate()`` control suite must pass before the tool joins the Tool Ocean.
"""
