import subprocess
import sys
from random import randint
import flask
import json
import os

filename = 'config/playlists.json'
# If playlists.json doesn't exist, create it
try:
    with open(filename, 'r') as f:
        pass
except FileNotFoundError:
    with open(filename, 'w') as f:
        json.dump([], f)


def get_config():
    with open(filename, 'r') as f:
        return json.load(f)


# Get each playlist. A playlist is a dictionary with a name, id, and path
def list_playlists(playlists):
    return [playlist['name'] for playlist in playlists]


def get_playlist_by_name(playlists, name):
    for playlist in playlists:
        if playlist['name'] == name:
            return playlist


def get_playlist_by_id(playlists, playlist_id):
    # playlist_id is an integer
    for playlist in playlists:
        if playlist['id'] == playlist_id:
            return playlist


def add_playlist(playlists, name):
    # To get the id, generate a random 5 digit number and check if it's in the list
    id = -1
    while id == -1:
        id = randint(0, 99999)
        for playlist in playlists:
            if playlist['id'] == id:
                id = -1
                break
    path = 'playlists/{}'.format(id)
    playlists.append({
        'name': name,
        'id': id,
        'path': path
    })
    with open(filename, 'w') as f:
        json.dump(playlists, f)
    return id


app = flask.Flask(__name__)


@app.route('/playlists/list')
def list_playlists_route():
    return flask.jsonify(list_playlists(get_config()))


@app.route('/playlists/get')
def get_playlist_by_id_route():
    playlist_id = int(flask.request.args.get('id'))
    return flask.jsonify(get_playlist_by_id(get_config(), playlist_id))


@app.route('/playlists/add', methods=['POST'])
def add_playlist_route():
    prev_config = get_config()
    data = flask.request.get_data()
    # The request body should contain a url
    # The args should contain a name
    name = flask.request.args.get('name')
    url = data.decode('utf-8')
    playlist_id = add_playlist(get_config(), name)
    # If the playlists folder doesn't exist, create it
    try:
        os.mkdir('playlists')
    except FileExistsError:
        pass
    # Make a directory using the id
    playlist_path = get_playlist_by_id(get_config(), playlist_id)['path']
    os.mkdir(playlist_path)

    # Download the playlist
    command = subprocess.Popen(f"{sys.executable} -m spotdl sync {url} --save-file sync.spotdl", shell=True, cwd=playlist_path)
    return_code = command.wait()

    # If we get a non-zero return code, return a 500 and revert the config file
    if return_code != 0:
        with open(filename, 'w') as f:
            json.dump(prev_config, f)
        return flask.Response(status=500)

    # Return a 201 Created
    return flask.Response(status=201)


@app.route('/playlists/delete')
def delete_playlist_route():
    playlist_id = int(flask.request.args.get('id'))
    playlist = get_playlist_by_id(get_config(), playlist_id)
    # Delete the directory
    subprocess.Popen(f"rm -rf {playlist['path']}", shell=True)
    # Delete the playlist from the config
    prev_config = get_config()
    new_config = [playlist for playlist in prev_config if playlist['id'] != playlist_id]
    with open(filename, 'w') as f:
        json.dump(new_config, f)
    return flask.Response(status=200)


@app.route('/playlists/download')
def download_playlists_route():
    playlist_id = int(flask.request.args.get('id'))
    playlist = get_playlist_by_id(get_config(), playlist_id)
    if playlist is None:
        return flask.Response(status=404)

    playlist_path = playlist['path']

    # Compress the playlist into a tar.gz file
    command = subprocess.Popen(f"tar -czvf {playlist_id}.tar.gz {playlist_id}", shell=True, cwd=os.path.dirname(playlist_path))
    return_code = command.wait()

    @flask.after_this_request
    def remove_zip(response):
        try:
            os.remove(f"{playlist_path}.tar.gz")
        except Exception as error:
            app.logger.error("Error removing or closing downloaded zip file", error)
        return response

    if return_code != 0:
        return flask.Response(status=500)
    else:
        # Path of the zip is the current working directory + the playlist path + .tar.gz
        fpath = os.path.join(os.getcwd(), f"{playlist_path}.tar.gz")
        return flask.send_file(fpath, as_attachment=True, download_name=f"{playlist['name']}.tar.gz")

@app.route('/playlists/sync_all')
def sync_all_playlists_route():
    playlists = get_config()
    for playlist in playlists:
        command = subprocess.Popen(f"{sys.executable} -m spotdl sync sync.spotdl", shell=True, cwd=playlist['path'])
        return_code = command.wait()
        if return_code != 0:
            return flask.Response(status=500)
    return flask.Response(status=200)

if __name__ == '__main__':
    app.run(port=44380)
