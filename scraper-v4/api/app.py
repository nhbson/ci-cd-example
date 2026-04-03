from flask import Flask, request, jsonify
import redis
import json

app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

QUEUE = "scraper:tasks"

@app.route("/")
def home():
    return {
        "status": "✅ Scraper V4 API Running",
        "message": "System is healthy 🚀",
        "endpoints": {
            "POST /add-task": "Add scraping tasks",
            "GET /stats": "Queue stats"
        }
    }

@app.route("/test")
def test():
    return "TEST OK"

@app.route("/add-task", methods=["POST"])
def add_task():
    data = request.json

    for keyword in data.get("keywords", []):
        task = {"query": keyword}
        r.lpush(QUEUE, json.dumps(task))

    return jsonify({"status": "queued", "count": len(data.get("keywords", []))})

@app.route("/stats")
def stats():
    return jsonify({
        "queue_length": r.llen(QUEUE)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)