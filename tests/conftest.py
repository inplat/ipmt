import os
import io
import time
import uuid
import shutil
import socket
import psycopg2
import pytest
from ipmt.migration import Repository
from docker.client import DockerClient
from docker.utils import kwargs_from_env


@pytest.fixture()
def repository(tmpdir):
    path = str(tmpdir.mkdir("sub"))
    rep = Repository.load(path)
    yield rep
    shutil.rmtree(path)


@pytest.fixture(params=["9.5", "9.6", "10.1"])
def database(request):
    host = '127.0.0.1'
    timeout = 300

    # getting free port
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    client = DockerClient(version='auto', **kwargs_from_env())
    client.images.pull('postgres', tag=request.param)
    cont = client.containers.run('postgres:%s' % request.param, detach=True,
                                 ports={'5432/tcp': ('127.0.0.1', port)})
    try:
        start_time = time.time()
        conn = None
        while conn is None:
            if start_time + timeout < time.time():
                raise Exception("Initialization timeout, failed to "
                                "initialize postgresql container")
            try:
                conn = psycopg2.connect('dbname=postgres user=postgres '
                                        'host=127.0.0.1 port=%d' % port)
            except psycopg2.OperationalError as e:
                time.sleep(.10)
        conn.close()
        yield (host, port, request.param)
    finally:
        cont.kill()
        cont.remove()


@pytest.fixture()
def tmpfile(tmpdir):
    perm_path = str(tmpdir.mkdir(str(uuid.uuid4())))
    perm_filename = os.path.join(perm_path, 'permissions.yml')
    f = io.open(perm_filename, 'w+', encoding="UTF8")
    yield f
    f.close()
    shutil.rmtree(perm_path)
