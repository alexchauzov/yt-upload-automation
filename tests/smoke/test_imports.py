import pytest


@pytest.mark.smoke
def test_import_domain():
    import domain.models
    import domain.services
    assert domain.models.Task is not None


@pytest.mark.smoke
def test_import_adapters():
    import adapters.google_sheets_repository
    import adapters.local_media_store
    assert adapters.google_sheets_repository.GoogleSheetsMetadataRepository is not None


@pytest.mark.smoke
def test_import_ports():
    import ports.metadata_repository
    import ports.media_uploader
    import ports.media_store
    assert ports.metadata_repository.MetadataRepository is not None


@pytest.mark.smoke
def test_import_app():
    import app.main
    assert app.main.main is not None
