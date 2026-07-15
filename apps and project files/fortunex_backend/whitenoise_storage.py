from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Identical to Whitenoise's CompressedManifestStaticFilesStorage,
    except it does not hard crash the entire page with a ValueError
    when ONE static file reference is missing from the hashed
    manifest. Instead it falls back to serving that one file's plain,
    unhashed path, and everything else still gets normal cache busted
    hashed filenames as usual.

    This exists specifically because of an open upstream bug in
    django-jazzmin 3.0.2 and newer:
    https://github.com/farridav/django-jazzmin/issues/661
    A couple of its new Bootswatch theme files get skipped during
    collectstatic's post-processing step ("... skipped due to
    conflict"), so they never make it into the manifest, and Django's
    default ManifestStaticFilesStorage raises instead of degrading
    gracefully for exactly that situation. manifest_strict = False is
    a real, documented Django setting for this, not a hack, it exists
    precisely to make this trade-off possible.
    """
    manifest_strict = False