import json
import urllib
import urlparse


from collections import defaultdict
from functools import wraps
from flask import request, current_app, render_template, render_template_string, jsonify

from alerta.app import app, db
from alerta.app.utils import crossdomain

LOG = app.logger


def jsonp(func):
    """Wraps JSONified output for JSONP requests."""
    @wraps(func)
    def decorated(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = str(func(*args, **kwargs).data)
            content = str(callback) + '(' + data + ')'
            mimetype = 'application/javascript'
            return current_app.response_class(content, mimetype=mimetype)
        else:
            return func(*args, **kwargs)
    return decorated


@app.route('/statuses/oembed.<format>', methods=['OPTIONS', 'GET'])
@crossdomain(origin='*', headers=['Origin', 'X-Requested-With', 'Content-Type', 'Accept'])
@jsonp
def oembed(format):

    if 'url' not in request.args or 'maxwidth' not in request.args \
        or 'maxheight' not in request.args:
        return jsonify(status="error", message="missing default parameters: url, maxwidth, maxheight, format"), 400

    try:
        url = request.args['url']
        width = int(request.args['maxwidth'])
        height = int(request.args['maxheight'])
        label = request.args.get('label', 'Alerts')
    except Exception as e:
        return jsonify(status="error", message=str(e)), 400

    if format != 'json':
        return jsonify(status="error", message="unsupported format: %s" % format), 400

    query = urlparse.urlparse(urllib.unquote(url).decode('utf8')).query
    if query != '':
        query = dict([x.split('=', 1) for x in query.split('&')])
    else:
        query = {}

    try:
        counts = db.get_counts(query=query)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

    found = 0
    severity_count = defaultdict(int)
    status_count = defaultdict(int)

    for count in counts:
        found += 1
        severity_count[count['severity']] += 1
        status_count[count['status']] += 1

    if severity_count['critical']:
        max_severity_class = 'severity-critical'
    elif severity_count['major']:
        max_severity_class = 'severity-major'
    elif severity_count['minor']:
        max_severity_class = 'severity-minor'
    elif severity_count['warning']:
        max_severity_class = 'severity-warning'
    elif severity_count['normal']:
        max_severity_class = 'severity-normal'
    else:
        max_severity_class = 'severity-normal'

    html = render_template('oembed/severity.html',
                           label=label,
                           width=width,
                           height=height,
                           severity_count=severity_count,
                           max_severity_class=max_severity_class
    )

    return jsonify(type="rich", version="1.0", width=width, height=height, html=html)