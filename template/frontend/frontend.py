from bottle import route, run, static_file, response
import os

SERVER_LIST = os.getenv('SERVER_LIST')
GROUP_NAME = os.getenv('GROUP_NAME')

@route('/')
@route('/server/<server>')
def index(server=0):
    with open('src/index.html') as f:
        s = f.read()
        s = s.replace("%SERVER_LIST%", SERVER_LIST)  # replace list of servers
        s = s.replace("%SERVER_ID%", str(server))  # replace selected server
        s = s.replace("%GROUP_NAME%", GROUP_NAME)  # replace group name
        return s

@route('/<filename:path>')
def serve_static_file(filename):
    response = static_file(filename, root="./src/")
    response.set_header("Cache-Control", "max-age=0")
    return response

run(host='0.0.0.0', port=80, debug=False, server='paste')