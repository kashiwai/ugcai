// ============================================================
// UGC Engine - Monitoring Dashboard API
// ============================================================
// Add these routes to server/index.js or import as middleware
// Provides real-time stats for the React monitoring dashboard
// ============================================================

function addMonitoringRoutes(app, videoQueue) {

  // Dashboard stats
  app.get("/api/stats", async (req, res) => {
    try {
      const [completed, active, waiting, failed, delayed] = await Promise.all([
        videoQueue.getCompletedCount(),
        videoQueue.getActiveCount(),
        videoQueue.getWaitingCount(),
        videoQueue.getFailedCount(),
        videoQueue.getDelayedCount(),
      ]);

      // Get recent completions for throughput calc
      const recentJobs = await videoQueue.getCompleted(0, 100);
      const now = Date.now();
      const oneHourAgo = now - 3600000;
      const lastHour = recentJobs.filter(j =>
        j.finishedOn && j.finishedOn > oneHourAgo
      ).length;

      // Average processing time
      const durations = recentJobs
        .filter(j => j.finishedOn && j.processedOn)
        .map(j => j.finishedOn - j.processedOn)
        .slice(0, 50);
      const avgDuration = durations.length > 0
        ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length / 1000)
        : 0;

      // Model breakdown
      const modelCounts = {};
      recentJobs.slice(0, 200).forEach(j => {
        const model = j.data?.model || "unknown";
        modelCounts[model] = (modelCounts[model] || 0) + 1;
      });

      // Character breakdown
      const charCounts = {};
      recentJobs.slice(0, 200).forEach(j => {
        const char = j.data?.character || "unknown";
        charCounts[char] = (charCounts[char] || 0) + 1;
      });

      res.json({
        queue: { completed, active, waiting, failed, delayed, total: completed + active + waiting + failed },
        throughput: { last_hour: lastHour, avg_per_hour: lastHour, avg_duration_seconds: avgDuration },
        breakdown: { by_model: modelCounts, by_character: charCounts },
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Recent activity feed
  app.get("/api/activity", async (req, res) => {
    try {
      const limit = Math.min(parseInt(req.query.limit) || 20, 100);
      const [completed, failed, active] = await Promise.all([
        videoQueue.getCompleted(0, limit),
        videoQueue.getFailed(0, 5),
        videoQueue.getActive(0, 5),
      ]);

      const activity = [
        ...completed.map(j => ({
          type: "completed",
          jobId: j.data?.jobId,
          character: j.data?.character,
          model: j.data?.model,
          duration: j.finishedOn && j.processedOn
            ? Math.round((j.finishedOn - j.processedOn) / 1000) : null,
          timestamp: j.finishedOn ? new Date(j.finishedOn).toISOString() : null,
          output_key: j.returnvalue?.output_key,
        })),
        ...failed.map(j => ({
          type: "failed",
          jobId: j.data?.jobId,
          character: j.data?.character,
          model: j.data?.model,
          error: j.failedReason?.slice(0, 200),
          timestamp: j.finishedOn ? new Date(j.finishedOn).toISOString() : null,
        })),
        ...active.map(j => ({
          type: "active",
          jobId: j.data?.jobId,
          character: j.data?.character,
          model: j.data?.model,
          timestamp: j.processedOn ? new Date(j.processedOn).toISOString() : null,
        })),
      ].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));

      res.json({ activity: activity.slice(0, limit) });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Health + uptime
  app.get("/api/health", async (req, res) => {
    try {
      const queueHealth = await videoQueue.getWaitingCount();
      res.json({
        status: "healthy",
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        queue_waiting: queueHealth,
      });
    } catch (err) {
      res.status(503).json({ status: "unhealthy", error: err.message });
    }
  });
}

module.exports = { addMonitoringRoutes };
