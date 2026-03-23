const http = require("http");

// Helper to POST event to Laravel webhook
function sendToWebhook(event) {
    return new Promise((resolve, reject) => {
        const postData = JSON.stringify(event);

        const options = {
            hostname: "host.docker.internal", // points to your local Laravel host
            port: 8000,
            path: "/api/call-ai-logs",
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Content-Length": Buffer.byteLength(postData)
            }
        };

        const req = http.request(options, (res) => {
            let data = "";
            res.on("data", chunk => data += chunk);
            res.on("end", () => resolve({statusCode: res.statusCode, body: data}));
        });

        req.on("error", (e) => reject(e));
        req.write(postData);
        req.end();
    });
}

exports.handler = async (event) => {
    /*
    Expected event structure:
    {
      "agent": "Alice",
      "phone": "+84912345678",
      "status": "ended",      // always "ended" if clicking End Call
      "start_time": "2026-03-23T10:00:00Z",
      "result": "completed"  // optional, default to completed
    }
    */

    try {
        // Calculate end time & duration
        const endTime = new Date().toISOString();
        const startTime = event.start_time || endTime; // fallback if missing
        const durationSeconds = Math.floor((new Date(endTime) - new Date(startTime))/1000);

        const payload = {
            agent: event.agent,
            phone: event.phone,
            status: event.status || "ended",
            start_time: startTime,
            end_time: endTime,
            duration_seconds: durationSeconds,
            result: event.result || "completed"
        };

        const response = await sendToWebhook(payload);

        console.log("Webhook response:", response);

        return {
            statusCode: 200,
            body: JSON.stringify({message: "Call event sent", payload})
        };

    } catch (error) {
        console.error("Error sending call log:", error);
        return {statusCode: 500, body: JSON.stringify({error: error.message})};
    }
};