# Backblaze Uploader

Backblaze Uploader is a Python package that you can use in order to upload files to a Backblaze bucket from a remote URL or a local path.

### Install
```bash
pip install bbup
```

### Configure a Bucket
Sign in to your Backblaze account, create a bucket, create application keys and then configure **bbup**:

```bash
bbup configure
```

You can add as many buckets as you want. Beware that app keys are stored in plain text, so don't use this software on a shared computer.

### Upload Remote Files
Upload a remote file to the default bucket:
```bash
bbup remote-upload
```

Upload a remote file to a selected bucket:

```bash
bbup remote-upload --bucket mybucket
```

### Upload Local Files
Upload a local file to the default bucket:
```bash
bbup local-upload
```

Upload a remote file to a selected bucket:

```bash
bbup local-upload --bucket mybucket
```

### Uninstall
```bash
pip uninstall bbup
```