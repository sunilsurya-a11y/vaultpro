from flask import Flask, render_template

app = Flask(__name__)

@app.after_request
def add_header(response):
    response.headers['X-Robots-Tag'] = 'index, follow'
    return response

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\n", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
