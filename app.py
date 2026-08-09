from flask import Flask, render_template, Response

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/robots.txt')
def robots():
    content = "User-agent: *\nAllow: /\n"
    return Response(content, mimetype="text/plain")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
