// ============================================================
// UGC Engine - Railway API Server
// ============================================================
// Deploy: railway up
// Manages job queue, dispatches to RunPod GPU, stores results in R2
// ============================================================

const express = require("express");
const { Queue, Worker, QueueEvents } = require("bullmq");
const { S3Client, PutObjectCommand, GetObjectCommand } = require("@aws-sdk/client-s3");
const { getSignedUrl } = require("@aws-sdk/s3-request-presigner");
const crypto = require("crypto");
const { addMonitoringRoutes } = require("./monitoring");

const app = express();
app.use(express.json({ limit: "50mb" }));

// CORS for dashboard
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Headers", "Content-Type, x-api-key");
  res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(200);
  next();
});

// ---- Config (set these as Railway environment variables) ----
const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY || "";
const RUNPOD_ENDPOINT_ID = process.env.RUNPOD_ENDPOINT_ID || "";
const R2_ACCOUNT_ID = process.env.R2_ACCOUNT_ID || "";
const R2_ACCESS_KEY = process.env.R2_ACCESS_KEY || "";
const R2_SECRET_KEY = process.env.R2_SECRET_KEY || "";
const R2_BUCKET = process.env.R2_BUCKET || "ugc-engine";
const API_SECRET = process.env.API_SECRET || "change-me-in-production";
const PORT = process.env.PORT || 3000;
const BASE_URL = process.env.RAILWAY_PUBLIC_DOMAIN
  ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`
  : `http://localhost:${PORT}`;

// ---- R2 Client ----
const r2 = new S3Client({
  region: "auto",
  endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: { accessKeyId: R2_ACCESS_KEY, secretAccessKey: R2_SECRET_KEY },
});

// ---- Job Queue ----
const connection = { url: REDIS_URL };
const videoQueue = new Queue("video-generation", { connection });

// ---- Auth Middleware ----
function auth(req, res, next) {
  const token = req.headers["x-api-key"];
  if (token !== API_SECRET) return res.status(401).json({ error: "Unauthorized" });
  next();
}

// ---- RunPod Polling ----
// Poll RunPod status until job is done, then update BullMQ job
async function pollRunPodStatus(runpodJobId, bullJobId, maxWaitMs = 1800000) {
  const startTime = Date.now();
  const pollIntervalMs = 5000;

  while (Date.now() - startTime < maxWaitMs) {
    await new Promise(r => setTimeout(r, pollIntervalMs));

    try {
      const resp = await fetch(
        `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/${runpodJobId}`,
        {
          headers: { Authorization: `Bearer ${RUNPOD_API_KEY}` },
        }
      );

      if (!resp.ok) {
        console.warn(`[Poll] RunPod status check failed: ${resp.status}`);
        continue;
      }

      const data = await resp.json();
      const status = data.status; // IN_QUEUE | IN_PROGRESS | COMPLETED | FAILED | CANCELLED | TIMED_OUT

      console.log(`[Poll] Job ${runpodJobId} → ${status}`);

      if (status === "COMPLETED") {
        const output = data.output || {};
        const bullJob = await videoQueue.getJob(bullJobId);
        if (bullJob) {
          const result = {
            output_key: output.output_key || `outputs/${bullJobId}.mp4`,
            completed_at: new Date().toISOString(),
            duration_seconds: output.duration_seconds || null,
            model: output.model || bullJob.data.model,
          };
          await bullJob.moveToCompleted(result, bullJobId);
        }
        return { status: "completed", output };

      } else if (status === "FAILED" || status === "CANCELLED" || status === "TIMED_OUT") {
        const bullJob = await videoQueue.getJob(bullJobId);
        if (bullJob) {
          await bullJob.moveToFailed(
            new Error(`RunPod ${status}: ${JSON.stringify(data.error || {})}`),
            bullJobId
          );
        }
        return { status: "failed", error: data.error };
      }
      // IN_QUEUE / IN_PROGRESS → continue polling

    } catch (err) {
      console.warn(`[Poll] Error polling RunPod: ${err.message}`);
    }
  }

  // Timeout
  const bullJob = await videoQueue.getJob(bullJobId);
  if (bullJob) {
    await bullJob.moveToFailed(new Error("Polling timeout after 30 minutes"), bullJobId);
  }
  return { status: "timeout" };
}

// ---- Routes ----

// Health check
app.get("/", (req, res) => {
  res.json({ status: "ok", engine: "ugc-generation-engine", version: "1.1.0" });
});

// Get presigned upload URL for R2
app.post("/api/upload-url", auth, async (req, res) => {
  try {
    const { filename, contentType } = req.body;
    const key = `inputs/${Date.now()}-${filename}`;
    const command = new PutObjectCommand({
      Bucket: R2_BUCKET,
      Key: key,
      ContentType: contentType || "application/octet-stream",
    });
    const url = await getSignedUrl(r2, command, { expiresIn: 3600 });
    res.json({ url, key });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Submit single video job
app.post("/api/job", auth, async (req, res) => {
  try {
    const { face_image_key, audio_key, character, script, model } = req.body;
    const jobId = crypto.randomUUID();
    await videoQueue.add("generate", {
      jobId,
      face_image_key,
      audio_key,
      character: character || "default",
      script: script || "",
      model: model || "musetalk",
      status: "queued",
      created_at: new Date().toISOString(),
    }, { jobId });
    res.json({ jobId, status: "queued" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Submit batch of jobs
app.post("/api/batch", auth, async (req, res) => {
  try {
    const { jobs } = req.body;
    const results = [];
    for (const job of jobs) {
      const jobId = crypto.randomUUID();
      await videoQueue.add("generate", {
        jobId,
        face_image_key: job.face_image_key,
        audio_key: job.audio_key,
        character: job.character || "default",
        script: job.script || "",
        model: job.model || "musetalk",
        status: "queued",
        created_at: new Date().toISOString(),
      }, { jobId });
      results.push({ jobId, status: "queued" });
    }
    res.json({ count: results.length, jobs: results });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Check job status
app.get("/api/job/:jobId", auth, async (req, res) => {
  try {
    const job = await videoQueue.getJob(req.params.jobId);
    if (!job) return res.status(404).json({ error: "Job not found" });
    const state = await job.getState();
    res.json({
      jobId: req.params.jobId,
      status: state,
      data: job.data,
      result: job.returnvalue || null,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List recent jobs
app.get("/api/jobs", auth, async (req, res) => {
  try {
    const completed = await videoQueue.getCompleted(0, 50);
    const active = await videoQueue.getActive(0, 10);
    const waiting = await videoQueue.getWaiting(0, 10);
    const failed = await videoQueue.getFailed(0, 10);
    res.json({
      completed: completed.length,
      active: active.length,
      waiting: waiting.length,
      failed: failed.length,
      recent: completed.slice(0, 20).map(j => ({
        jobId: j.data.jobId,
        character: j.data.character,
        model: j.data.model,
        result: j.returnvalue,
      })),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get download URL for completed video
app.post("/api/download-url", auth, async (req, res) => {
  try {
    const { key } = req.body;
    const command = new GetObjectCommand({ Bucket: R2_BUCKET, Key: key });
    const url = await getSignedUrl(r2, command, { expiresIn: 3600 });
    res.json({ url });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Callback from RunPod worker (kept for compatibility)
app.post("/api/callback", async (req, res) => {
  try {
    const { jobId, status, output_key, error } = req.body;
    const job = await videoQueue.getJob(jobId);
    if (job) {
      if (status === "completed") {
        await job.moveToCompleted(
          { output_key, completed_at: new Date().toISOString() },
          job.id
        );
      } else if (status === "failed") {
        await job.moveToFailed(new Error(error || "Unknown error"), job.id);
      }
    }
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---- Worker: Dispatch to RunPod ----
const worker = new Worker("video-generation", async (job) => {
  const { jobId, face_image_key, audio_key, model } = job.data;
  console.log(`[Worker] Processing job ${jobId} with model ${model}`);

  // Call RunPod Serverless API
  const response = await fetch(`https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${RUNPOD_API_KEY}`,
    },
    body: JSON.stringify({
      input: {
        job_id: jobId,
        face_image_key,
        audio_key,
        model,
        r2_bucket: R2_BUCKET,
        r2_endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
        r2_access_key: R2_ACCESS_KEY,
        r2_secret_key: R2_SECRET_KEY,
        callback_url: `${BASE_URL}/api/callback`,
      },
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`RunPod API error ${response.status}: ${errText}`);
  }

  const result = await response.json();
  const runpodJobId = result.id;

  if (!runpodJobId) {
    throw new Error(`RunPod did not return a job ID: ${JSON.stringify(result)}`);
  }

  console.log(`[Worker] RunPod job started: ${runpodJobId}`);

  // Start async polling (non-blocking - don't await here)
  pollRunPodStatus(runpodJobId, jobId).then(r => {
    console.log(`[Poll] Job ${jobId} finished with status: ${r.status}`);
  }).catch(err => {
    console.error(`[Poll] Polling error for ${jobId}: ${err.message}`);
  });

  return { runpod_id: runpodJobId, status: "dispatched" };
}, { connection, concurrency: 10 });

worker.on("completed", (job) => {
  console.log(`[Worker] Job ${job.data.jobId} dispatched to RunPod`);
});

worker.on("failed", (job, err) => {
  console.error(`[Worker] Job ${job?.data?.jobId} failed: ${err.message}`);
});

// ---- Monitoring Routes ----
addMonitoringRoutes(app, videoQueue);

// ---- Start Server ----
app.listen(PORT, () => {
  console.log(`UGC Engine API running on port ${PORT}`);
  console.log(`Base URL: ${BASE_URL}`);
});
