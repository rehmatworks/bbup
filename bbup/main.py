import json
from pathlib import Path
import tempfile
from typing import Optional

import typer
from typer import prompt as p
from typer import Option as o
import validators
import requests

# Backblaze SDK
from b2sdk.v2 import (
    InMemoryAccountInfo, B2Api
)
from b2sdk.exception import RestrictedBucket

# Create Typer app instance
app = typer.Typer()

APP_NAME = 'bbuploader'
APP_BASE_DIR: Path = Path(typer.get_app_dir(APP_NAME))
CHUNK_SIZE = 1024
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}


def authorize_b2(key_id, app_key, bucket):
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    try:
        b2_api.authorize_account('production', key_id, app_key)
    except RestrictedBucket:
        raise typer.Exit(typer.style(text='The application key should be allowed to access all buckets. Is it restricted?', fg=typer.colors.RED))
    
    bucket = b2_api.get_bucket_by_name(bucket)
    return b2_api, bucket


def load_conf_data():
    conf_data = []
    
    # Get existing conf data
    conf_file: Path = APP_BASE_DIR / 'config.json'
    if conf_file.is_file():
        with open(conf_file) as f:
            try:
                conf_data = json.loads(f.read())
                if type(conf_data) is not list:
                    conf_data = []
            except:
                pass
            
    return conf_data

@app.command(help='Configure Backblaze bucket settings.')
def configure(set_default: bool = o(prompt='Do you want to set this bucket as default?', default=False), use_domain: bool = o(prompt='Do you want to use a custom domain?', default=False)):
    # Create conf dir if missing
    if not APP_BASE_DIR.is_dir():
        APP_BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    bucket: str = str(p('Bucket name')).strip()
    id: str = str(p('Backblaze keyID')).strip()
    key: str = str(p('Backblaze applicationKey')).strip()
    domain = None
    
    if use_domain:
        while domain is None:
            domain = str(p('Domain/Subdomain')).strip()
            if not validators.domain(domain):
                typer.echo(typer.style(text='Provided domain is invalid.', fg=typer.colors.YELLOW))
                domain = None
    
    conf_file: Path = APP_BASE_DIR / 'config.json'
    conf_data = load_conf_data()
    try:
        authorize_b2(id, key, bucket)
    except Exception as e:
        raise typer.Exit(typer.style(text=str(e), fg=typer.colors.RED))
    
    if domain:
        url = f'https://{domain}/file/{bucket}'
    else:
        url = None
    conf_obj = {
        'bucket': bucket,
        'app_key': key,
        'app_id': id,
        'is_default': set_default,
        'url': url
    }
    
    # Delete if conf exists
    i = 0
    for item in conf_data:
        if set_default and item.get('is_default'):
            conf_data[i]['is_default'] = False
            
        if item.get('bucket') == bucket:
            del conf_data[i]
        i += 1
    
    conf_data.append(conf_obj)
    
    with open(conf_file, 'w') as f:
        try:
            f.write(json.dumps(conf_data))
            typer.echo(typer.style(text=f'Settings for the bucket {bucket} have been saved successfully.', fg=typer.colors.GREEN))
        except:
            raise typer.Exit(typer.style(text='Configuration settings cannot be saved.', fg=typer.colors.RED))

def do_upload(path, save_as, bucket, content_type=None):
    if not Path(path).is_file:
        raise typer.Exit(typer.style(text=f'Local file path [{path}] does not exist.', fg=typer.colors.YELLOW))
    try:
        bucket.upload_local_file(local_file=path, file_name=save_as, content_type=content_type)
        return True
    except:
        return False
    

def get_bucket(bucket):
    bucket_obj = None
    try:
        conf_data = load_conf_data()
        if bucket:
            bucket_obj = list(filter(lambda item: item if item.get('bucket') == bucket else None, conf_data))[0]
        else:
            bucket_obj = list(filter(lambda item: item if item.get('is_default') else None, conf_data))[0]
    except IndexError:
        bucket_obj = None
        if bucket:
            text = f'The provided bucket {bucket} cannot be found. Please provide a valid bucket name.'
        else:
            text = f'A default bucket cannot be found. Please provide a bucket name.'
        typer.echo(typer.style(text=text, fg=typer.colors.YELLOW))
        
        while bucket_obj is None:
            bucket = p('Bucket name')
            try:
                bucket_obj = list(filter(lambda item: item if item.get('bucket') == bucket else None, conf_data))[0]
            except IndexError:
                typer.echo(typer.style(text=f'A bucket with name {bucket} cannot be found in config.', fg=typer.colors.YELLOW))
                bucket_obj = None
    
    if bucket_obj:
        try:
            typer.echo(typer.style(text='Authenticating Backblaze...', fg=typer.colors.BRIGHT_BLUE))
            id = bucket_obj.get('app_id')
            key = bucket_obj.get('app_key')
            bucket_name = bucket_obj.get('bucket')
            api, bucket = authorize_b2(id, key, bucket_name)
            typer.echo(typer.style(text='Authentication successful!', fg=typer.colors.GREEN))
        except Exception as e:
            raise typer.Exit(typer.style(text=str(e), fg=typer.colors.RED))
    
        return bucket_obj, bucket

    return None, None

def format_bytes(B):
    B = float(B)
    KB = float(1024)
    MB = float(KB ** 2) # 1,048,576
    GB = float(KB ** 3) # 1,073,741,824
    TB = float(KB ** 4) # 1,099,511,627,776
    
    if B < KB:
        return '{0}{1}'.format(B,'Bytes' if 0 == B > 1 else 'Byte')
    elif KB <= B < MB:
        return '{0:.2f}KB'.format(B / KB)
    elif MB <= B < GB:
        return '{0:.2f}MB'.format(B / MB)
    elif GB <= B < TB:
        return '{0:.2f}GB'.format(B / GB)
    elif TB <= B:
        return '{0:.2f}TB'.format(B / TB)

def get_file_size(path):
    try:
        return format_bytes(Path(path).stat().st_size)
    except:
        return format_bytes(0)

@app.command(help='Upload a file from a remote URL.')
def remote_upload(bucket: Optional[str] = None):
    url = None
    while url is None:
        url = str(p('Remote URL')).strip()
        if not validators.url(url):
            typer.echo(typer.style(text='The provided URL is invalid.', fg=typer.colors.YELLOW))
            url = None
    
    # Save as name
    path = Path(url)
    save_as = p('Save as', default=path.name)
    
    bucket_obj, bucket = get_bucket(bucket)

    typer.echo(typer.style(text=f'Downloading data from {url}', fg=typer.colors.BRIGHT_BLUE))
    
    if requests.head(url).status_code != 200:
        raise typer.Exit(typer.style(text='File cannot be downloaded from the provided URL.', fg=typer.colors.RED))

    content_type = None
    with tempfile.NamedTemporaryFile(mode='w+b') as f:
        with requests.get(url, stream=True, headers=HEADERS) as res:
            content_type = res.headers.get('Content-Type')
            try:
                total_size = int(res.headers.get('Content-Length'))
            except:
                total_size = 0
                
            with typer.progressbar(range(total_size)) as progress:
                for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    progress.update(CHUNK_SIZE)
        
        typer.echo(typer.style(text='Uploading file to Backblaze.', fg=typer.colors.BRIGHT_BLUE))       
        if do_upload(path=f.name, save_as=save_as, bucket=bucket, content_type=content_type):
            base_url = bucket_obj.get('url')
            if base_url:
                uploaded_url = f'{base_url}/{save_as}'
                message = f'File [{get_file_size(f.name)}] has been uploaded: {uploaded_url}'
            else:
                message = f'File [{get_file_size(f.name)}] has been successfully uploaded.'
                
            typer.echo(typer.style(text=message, fg=typer.colors.GREEN))
        else:
            typer.echo(typer.style(text=f'File upload failed. Please try again.', fg=typer.colors.YELLOW))
 
@app.command(help='Upload a file from a local path.')   
def local_upload(bucket: Optional[str] = None, content_type: Optional[str] = None):
    path: Path = Path(p('Local Path'))
    if not path.is_file():
        raise typer.Exit(typer.style(text=f'File cannot be found at path {path}', fg=typer.colors.YELLOW))
    
    save_as: str = p('Save as', default=path.name)
    bucket_obj, bucket = get_bucket(bucket)
    if do_upload(path=path, save_as=save_as, bucket=bucket, content_type=content_type):
        base_url = bucket_obj.get('url')
        if base_url:
            uploaded_url = f'{base_url}/{save_as}'
            message = f'File [{get_file_size(f.name)}] has been uploaded: {uploaded_url}'
        else:
            message = f'File [{get_file_size(f.name)}] has been successfully uploaded.'
                
        typer.echo(typer.style(text=message, fg=typer.colors.GREEN))
    else:
        typer.echo(typer.style(text=f'File upload failed. Please try again.', fg=typer.colors.YELLOW))

if __name__ == '__main__':
    app()