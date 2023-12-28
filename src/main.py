import subprocess
import sys
from random import randint
import flask
import json
import os

import pywebio.platform
import pywebio_battery
import requests
from pywebio.output import put_table, put_markdown, put_button, popup, close_popup, put_loading, put_scope, use_scope
from pywebio.platform.flask import webio_view

pywebio.platform.config(title="Music Server", theme="dark")

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
    return [playlist['id'] for playlist in playlists]


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


@app.route('/playlists/song_qty')
def get_song_qty_route():
    playlist_id = int(flask.request.args.get('id'))
    playlist = get_playlist_by_id(get_config(), playlist_id)
    if playlist is None:
        return flask.Response(status=404)

    playlist_path = playlist['path']

    # Get the number of songs in the playlist
    count = len(os.listdir(playlist_path)) - 1
    return flask.Response(str(count), status=200)


def delete_playlist_confirmation(playlist_id):
    if pywebio_battery.confirm("Are you sure you want to delete this playlist?"):
        # Delete the playlist
        requests.get(f"http://localhost:44380/playlists/delete?id={playlist_id}")
        # Clear the current page and reload it
        pywebio.output.clear()
        web_console()


def add_playlist_button(playlist_name, playlist_url):
    with pywebio.output.popup("Adding playlist..."):
        put_loading()
    requests.post(f"http://localhost:44380/playlists/add?name={playlist_name}", data=playlist_url.encode('utf-8'))
    close_popup()
    pywebio.output.popup("Playlist added!")
    pywebio.output.clear_scope("main")
    render_main()


def sync_all_playlists_button():
    with use_scope("info"):
        pywebio.output.put_info("Sync in progress...", closable=True)
        requests.get(f"http://localhost:44380/playlists/sync_all")
        pywebio.output.put_info("Sync complete!", closable=True)
    pywebio.output.clear_scope("main")
    render_main()


def download_playlist_button(playlist_id):
    with pywebio.output.popup("Preparing Download..."):
        put_loading()
        # Download the playlist
        content = requests.get(f"http://localhost:44380/playlists/download?id={playlist_id}").content
        pywebio.session.download("playlist.tar.gz", content)
    close_popup()


def render_main():
    with use_scope("main"):
        put_markdown("# Music Server")
        put_markdown("## Playlists")
        # Create a table of playlists with their names
        playlists = get_config()

        # Get a copy of the playlists without the path
        playlists_copy = []
        for playlist in playlists:
            playlist_qty = requests.get(f"http://localhost:44380/playlists/song_qty?id={playlist['id']}")
            playlists_copy.append([
                playlist['name'],
                playlist['id'],
                str(playlist_qty.text),
                put_button('Delete', color="danger", onclick=lambda: delete_playlist_confirmation(playlist['id'])),
                put_button('Download', color="primary", onclick=lambda: download_playlist_button(playlist['id']))
            ])

        put_table(playlists_copy, header=['Name', 'ID', 'Songs'])

        put_button("Sync All Playlists", onclick=sync_all_playlists_button)

        put_markdown("## Add Playlist")
        # Create a form to add a playlist
        put_markdown("### Playlist Name")
        pywebio.pin.put_input("playlist_name", type="text")
        put_markdown("### Playlist URL")
        pywebio.pin.put_input("playlist_url", type="text")
        put_button("Add Playlist", onclick=lambda: add_playlist_button(pywebio.pin.pin['playlist_name'], pywebio.pin.pin['playlist_url']))


def web_console():
    put_scope("info")
    put_scope("main")
    render_main()


app.add_url_rule('/', 'webio_view', webio_view(web_console),methods=['GET','POST'])

if __name__ == '__main__':
    app.run(port=44380, host="0.0.0.0")
