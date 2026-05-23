import React, { useState } from "react";


import axios from "axios";

// ---- helpers for safe rendering ----
const getScore = (clip) => (clip?.score ?? clip?.viral_score ?? 0);
const getDuration = (clip) => {
  if (clip?.duration) return Math.round(clip.duration);
  if (clip?.start != null && clip?.end != null) return Math.max(0, Math.round(clip.end - clip.start));
  return 0;
};
const getNiche = (clip) => (clip?.niche || clip?.category || "general");
const getTitle = (clip, idx) => (clip?.title || clip?.source_text?.slice(0, 80) || `Clip #${idx + 1}`);
const getHashtags = (clip) => (Array.isArray(clip?.hashtags) ? clip.hashtags : []);

const hasClipResults = (result) => {
  const clips = Array.isArray(result?.clips) ? result.clips : [];
  const finalClips = Array.isArray(result?.final_clips) ? result.final_clips : [];
  return clips.length > 0 || finalClips.length > 0;
};

const isNoCreatorSafeClipsResult = (result) => {
  const message = String(result?.message || "").toLowerCase();
  return !hasClipResults(result) && message.includes("no creator-safe clips found");
};

const getCreatorQaSummary = (result) => {
  const summary = result?.summary || {};
  const creatorQa = result?.creator_qa || {};
  return {
    rejectedByCreatorQa:
      summary.rejected_by_creator_qa ??
      creatorQa.rejections?.length ??
      0,
    topRejectionReasons:
      summary.top_rejection_reasons ||
      creatorQa.top_rejection_reasons ||
      [],
  };
};

const getResultPayload = (data) => {
  const workerResult = data?.worker_status?.result || {};
  return data?.result || workerResult || data || {};
};

const clipFromFinalPath = (path, idx) => ({
  clip_number: idx + 1,
  title: `Clip #${idx + 1}`,
  video_url: path,
  video_path: path,
  download_url: path,
  score: 0,
  niche: "general",
  duration: 0,
  hashtags: [],
});

const getCompatibleClips = (...sources) => {
  for (const source of sources) {
    if (!source) continue;
    if (Array.isArray(source.clips) && source.clips.length > 0) return source.clips;
    if (Array.isArray(source.result?.clips) && source.result.clips.length > 0) return source.result.clips;
    if (Array.isArray(source.worker_status?.clips) && source.worker_status.clips.length > 0) return source.worker_status.clips;
    if (Array.isArray(source.worker_status?.result?.clips) && source.worker_status.result.clips.length > 0) {
      return source.worker_status.result.clips;
    }
  }

  for (const source of sources) {
    if (!source) continue;
    const finalClips =
      source.final_clips ||
      source.result?.final_clips ||
      source.worker_status?.final_clips ||
      source.worker_status?.result?.final_clips ||
      [];
    if (Array.isArray(finalClips) && finalClips.length > 0) {
      return finalClips.filter(Boolean).map(clipFromFinalPath);
    }
  }

  return [];
};

const getNoClipReason = (result) => {
  if (!result) return "";
  if (result.error) return result.error;
  if (result.message) return result.message;
  const summary = getCreatorQaSummary(result);
  if (summary.rejectedByCreatorQa > 0) {
    const reasons = summary.topRejectionReasons.map(formatRejectionReason).join(", ");
    return `Creator QA rejected ${summary.rejectedByCreatorQa} candidate(s)${reasons ? `: ${reasons}` : ""}`;
  }
  return "";
};

const formatRejectionReason = (reason) => {
  if (Array.isArray(reason)) return reason.join(": ");
  if (reason && typeof reason === "object") {
    return Object.entries(reason).map(([key, value]) => `${key}: ${value}`).join(", ");
  }
  return String(reason);
};


const API = "http://127.0.0.1:8000";

function fixVideoUrl(path) {
  if (!path) return "";

  let clean = String(path).replace(/\\/g, "/");

  const uploadsIndex = clean.indexOf("uploads/");
  if (uploadsIndex !== -1) clean = clean.substring(uploadsIndex);

  const outputsIndex = clean.indexOf("outputs/");
  if (outputsIndex !== -1) clean = clean.substring(outputsIndex);

  return `${API}/${clean}`;
}

function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [jobs, setJobs] = useState([]);
  const [status, setStatus] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [feedbackState, setFeedbackState] = useState({});
  const [error, setError] = useState("");
  const [processProgress, setProcessProgress] = useState(0);
  const [smoothProgress, setSmoothProgress] = useState(0);

  // Smooth progress animation
  React.useEffect(() => {
    if (processProgress > smoothProgress) {
      const interval = setInterval(() => {
        setSmoothProgress(prev => {
          if (prev >= processProgress) {
            clearInterval(interval);
            return processProgress;
          }
          return prev + 1;
        });
      }, 30);

      return () => clearInterval(interval);
    }
  }, [processProgress, smoothProgress]);


  const pollJob = async (id) => {
    const timer = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/status/${id}`);
        const data = res.data;

        setJobs(prev =>
  prev.map(j =>
    j.id === id
      ? {
          ...j,
          status: data.status || "processing",
          progress: data.progress || j.progress,
          stage: data.stage || j.stage
        }
      : j
  )
);
        setCurrentStage(data.stage || "");
        setProcessProgress(data.progress || 0);

        if (data.status === "completed" || data.status === "done") {
          clearInterval(timer);
          setLoading(false);

          const finalResult = getResultPayload(data);
          const normalizedClips = getCompatibleClips(data, finalResult, data.worker_status);
          const normalizedFinalClips =
            data.final_clips ||
            data.worker_status?.final_clips ||
            data.worker_status?.result?.final_clips ||
            finalResult.final_clips ||
            [];
          const completedResult = { ...finalResult, clips: normalizedClips, final_clips: normalizedFinalClips };
          const noCreatorSafeClips = isNoCreatorSafeClipsResult(completedResult);
          const completedStage = noCreatorSafeClips
            ? "⚠ No creator-safe clips found"
            : normalizedClips.length > 0
              ? "✅ Final clips ready!"
              : (getNoClipReason(completedResult) || "Completed with no clips");

          setResult(completedResult);

          setJobs(prev =>
            prev.map(j =>
              j.id === id
                ? {
                    ...j,
                    status: "completed",
                    stage: completedStage,
                    progress: 100,
                    clips: normalizedClips,
                    final_clips: normalizedFinalClips,
                    result: completedResult
                  }
                : j
            )
          );
        }

        if (
          data.status === "failed" ||
          data.status === "error" ||
          data.status === "not_found" ||
          data.status === "worker_status_error"
        ) {
          clearInterval(timer);
          setLoading(false);
          setError(data.error || "Processing failed");
        }
      } catch (err) {
        clearInterval(timer);
        setLoading(false);
        setError("Could not fetch job status");
      }
    }, 3000);
  };

  const uploadFile = async () => {
  if (!file) {
    alert("Select video first");
    return;
  }

  try {
    setLoading(true);
    setResult(null);
    setError("");
    setUploadProgress(0);
    setCurrentStage("⚡ Creating instant job...");
    setStatus("creating_job");

    // STEP 1: instant job_id
    const jobRes = await axios.post(`${API}/create-job`);
    const newJobId = jobRes.data?.job_id;

    if (!newJobId) {
      throw new Error("Failed to create job");
    }

    setJobs(prev => [
  {
    id: newJobId,
    status: "uploading",
    progress: 0,
    stage: "📤 Uploading..."
  },
  ...prev
]);
    setCurrentStage("📤 Uploading video to server...");
    setStatus("uploading");

    // STEP 2: upload with job_id
    const formData = new FormData();
    formData.append("file", file);

    await axios.post(`${API}/upload/${newJobId}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);

          setJobs(prev =>
            prev.map(j =>
              j.id === newJobId
                ? {
                    ...j,
                    status: "uploading",
                    stage: "📤 Uploading...",
                    progress: percent
                  }
                : j
            )
          );
        }
      },
    });

    setUploadProgress(100);
    setCurrentStage("⏳ Upload complete. Waiting for processor...");
    setStatus("queued");

    // STEP 3: start polling
    pollJob(newJobId);

  } catch (err) {
    console.error(err);
    setLoading(false);
    setError("Upload failed");
  }
};


  const submitFeedback = async (jobId, clipIndex, rating, reason = "") => {
    const key = `${jobId}_${clipIndex}`;

    try {
      setFeedbackState(prev => ({
        ...prev,
        [key]: { status: "saving", rating, reason }
      }));

      await axios.post(`${API}/feedback`, {
        job_id: jobId,
        clip_index: clipIndex,
        rating,
        reason,
        note: reason
      });

      setFeedbackState(prev => ({
        ...prev,
        [key]: { status: "saved", rating, reason }
      }));
    } catch (err) {
      setFeedbackState(prev => ({
        ...prev,
        [key]: { status: "error", rating, reason }
      }));
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top left, #1e293b, #020617 55%)",
        color: "white",
        fontFamily: "Inter, Arial, sans-serif",
        padding: "clamp(14px, 2vw, 24px)",
      }}
    >
      <div
        style={{
          maxWidth: "1180px",
          margin: "0 auto",
        }}
      >
        {/* NAV */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "22px",
          }}
        >
          <div
            style={{
              fontSize: "clamp(30px, 4vw, 38px)",
              fontWeight: "950",
              letterSpacing: "-1px",
              color: "#f8fafc",
              textShadow: "0 0 35px rgba(56,189,248,0.35)",
            }}
          >
            Flux<span style={{ color: "#38bdf8" }}>Clip</span>
            <div
              style={{
                fontSize: "11px",
                color: "#94a3b8",
                letterSpacing: "1.6px",
                marginTop: "4px",
                fontWeight: "800",
              }}
            >
              ⚡ AI SHORTS ENGINE
            </div>
          </div>

          <div
            style={{
              display: "flex",
              gap: "16px",
              color: "#cbd5e1",
              fontSize: "14px",
              fontWeight: "700",
            }}
          >
            <span>Dashboard</span>
            <span>Pricing</span>
            <span>Docs</span>
          </div>
        </div>

        {/* CENTER HERO */}
        <div
          style={{
            textAlign: "center",
            maxWidth: "980px", width: "100%",
            margin: "0 auto clamp(16px, 3vw, 26px)",
            padding: "clamp(6px, 1vw, 10px) 10px clamp(2px, 0.8vw, 6px)",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              padding: "8px 14px",
              borderRadius: "999px",
              background: "rgba(15,23,42,0.78)",
              border: "1px solid rgba(148,163,184,0.22)",
              color: "#cbd5e1",
              fontSize: "13px",
              fontWeight: "900",
              letterSpacing: "0.3px",
              marginBottom: "18px",
            }}
          >
            India's First AI Auto Shorts Maker Viral Engine
          </div>

          <div style={{position:'fixed',bottom:8,right:8,zIndex:99999,fontSize:12,background:'#16a34a',color:'white',padding:'6px 10px',borderRadius:8}}></div>\n      <h1
            style={{
              fontSize: "clamp(32px, 6vw, 60px)",
              lineHeight: "1.0",
              margin: "0",
              fontWeight: "950",
              letterSpacing: "-2.4px",
              color: "#f8fafc",
            }}
          >
            Turn long videos into viral-ready shorts.
          </h1>

          <p
            style={{
              maxWidth: "700px", width: "100%",
              margin: "clamp(8px, 1.5vw, 14px) auto 0",
              color: "#94a3b8",
              fontSize: "clamp(15px, 1.7vw, 18px)",
              lineHeight: "1.7",
            }}
          >
            AI that finds, cuts and optimizes viral moments automatically — made in India, made for the world.
          </p>
        </div>

        {/* UPLOAD CENTER CARD */}
        <div
          style={{
            maxWidth: "760px",
            margin: "0 auto 34px",
            background: "rgba(15,23,42,0.92)",
            border: "1px solid rgba(148,163,184,0.22)",
            borderRadius: "28px",
            padding: "clamp(18px, 4vw, 30px)",
            boxShadow: "0 35px 110px rgba(0,0,0,0.46)",
          }}
        >
          <h2 style={{ marginTop: 0, textAlign: "center", fontSize: "clamp(24px, 3vw, 30px)" }}>
            Create New Viral Pack
          </h2>

          <p style={{ color: "#94a3b8", textAlign: "center", fontSize: "16px" }}>
            Upload one long-form video to generate AI-selected short clips.
          </p>

          <div
            style={{
              border: "2px dashed rgba(148,163,184,0.35)",
              borderRadius: "20px",
              padding: "clamp(18px, 4vw, 30px)",
              textAlign: "center",
              background: "rgba(30,41,59,0.58)",
              margin: "14px 0",
            }}
          >
            {previewUrl ? (
              <video
                src={previewUrl}
                style={{
                  width: "100%",
                  maxHeight: "170px",
                  objectFit: "cover",
                  borderRadius: "16px",
                  marginBottom: "12px",
                  background: "#020617",
                }}
                muted
                controls={false}
              />
            ) : (
              <div style={{ fontSize: "44px", marginBottom: "12px" }}>🎬</div>
            )}

            <input
              type="file"
              onChange={(e) => {
                const f = e.target.files[0];
                setFile(f);
                if (f) {
                  const url = URL.createObjectURL(f);
                  setPreviewUrl(url);
                }
              }}
            />

            <p style={{ color: "#cbd5e1", fontSize: "14px" }}>
              {file ? file.name : "MP4, MOV, MKV supported"}
            </p>
          </div>

          <button
            onClick={uploadFile}
            disabled={false}
            style={{
              width: "100%",
              background: "linear-gradient(135deg, #22c55e, #38bdf8)",
              boxShadow: "0 0 24px rgba(56,189,248,0.32)",
              color: "white",
              border: "none",
              padding: "clamp(14px, 2vw, 16px) 20px",
              borderRadius: "16px",
              cursor: "pointer",
              fontWeight: "950",
              fontSize: "17px",
            }}
          >
            Generate Viral Shorts
          </button>

          {jobs.length > 0 && (
            <div style={{ marginTop: "18px" }}>
              {jobs.map((job) => (
                <div
                  key={job.id}
                  style={{
                    marginBottom: "12px",
                    background: "rgba(30,41,59,0.8)",
                    borderRadius: "14px",
                    padding: "14px",
                    fontSize: "14px",
                    border: "1px solid rgba(148,163,184,0.2)",
                  }}
                >
                  <div>
                    <strong>Status:</strong> {job.status}
                  </div>

                  <div style={{ marginTop: "6px", color: "#22c55e" }}>
                    {job.stage} {job.progress > 0 ? `(${job.progress}%)` : ""}
                  </div>

                  <div
                    style={{
                      height: "10px",
                      width: "100%",
                      background: "rgba(148,163,184,0.22)",
                      borderRadius: "999px",
                      overflow: "hidden",
                      border: "1px solid rgba(148,163,184,0.25)",
                      marginTop: "10px",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${job.progress || 0}%`,
                        background: "linear-gradient(90deg, #22c55e, #38bdf8)",
                        borderRadius: "999px",
                        transition: "width 0.35s ease",
                      }}
                    />
                  </div>

                  <div style={{ color: "#94a3b8", marginTop: "8px" }}>
                    Job: {job.id}
                  </div>

                  {isNoCreatorSafeClipsResult(job.result) && (
                    <div
                      style={{
                        marginTop: "10px",
                        padding: "10px",
                        borderRadius: "10px",
                        background: "rgba(120,53,15,0.28)",
                        border: "1px solid rgba(251,191,36,0.28)",
                        color: "#fde68a",
                        lineHeight: "1.5",
                      }}
                    >
                      <div style={{ fontWeight: "900" }}>
                        Rejected by Creator QA: {getCreatorQaSummary(job.result).rejectedByCreatorQa}
                      </div>
                      {getCreatorQaSummary(job.result).topRejectionReasons.length > 0 && (
                        <div style={{ marginTop: "4px", color: "#fef3c7" }}>
                          Top reasons: {getCreatorQaSummary(job.result).topRejectionReasons.map(formatRejectionReason).join(", ")}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* STATS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "16px",
            marginBottom: "28px",
          }}
        >
          {[
            ["⚡", "Fast ASR", "GPU optimized"],
            ["🧠", "Viral Brain", "Hook ranking"],
            ["🎯", "Smart Export", "Captions + titles"],
            ["📦", "Creator Pack", "Download ready"],
          ].map(([icon, title, sub]) => (
            <div
              key={title}
              style={{
                background: "rgba(15,23,42,0.8)",
                border: "1px solid rgba(148,163,184,0.18)",
                borderRadius: "18px",
                padding: "20px",
              }}
            >
              <div style={{ fontSize: "clamp(24px, 3vw, 30px)" }}>{icon}</div>
              <h3 style={{ margin: "10px 0 6px" }}>{title}</h3>
              <p style={{ color: "#94a3b8", margin: 0 }}>{sub}</p>
            </div>
          ))}
        </div>

        {loading && (
          <div
            style={{
              background: "rgba(34,197,94,0.12)",
              border: "1px solid rgba(34,197,94,0.35)",
              padding: "22px",
              borderRadius: "18px",
              marginBottom: "28px",
            }}
          >
            <h3>🔥 AI is cooking your viral clips...</h3>
            <p style={{ color: "#cbd5e1" }}>
              Transcribing → Viral Detection → Smart Crop → Captions → Final
              Shorts
            </p>
          </div>
        )}

        {error && (
          <div
            style={{
              background: "#7f1d1d",
              padding: "18px",
              borderRadius: "16px",
              marginBottom: "24px",
            }}
          >
            {error}
          </div>
        )}

        {jobs.some(j => getCompatibleClips(j, j.result).length > 0) && (
          <div>
            <h2 style={{ fontSize: "28px" }}>Your Viral Clips</h2>

            {jobs.map((job) => {
              const jobClips = getCompatibleClips(job, job.result);

              if (!jobClips.length) return null;

              return (
                <div key={job.id} style={{ marginBottom: "36px" }}>
                  <div
                    style={{
                      fontSize: "13px",
                      color: "#94a3b8",
                      marginBottom: "12px",
                    }}
                  >
                    Job ID: {job.id}
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(280px, 360px))",
                      gap: "20px",
                    }}
                  >
                    {jobClips.map((clip, index) => {
                      const videoUrl = fixVideoUrl(
                        clip.video_url || clip.video_path || clip.download_url || clip.path || clip.file || clip.url
                      );

                      return (
                        <div
                          key={`${job.id}-${index}`}
                          style={{
                            background: "rgba(15,23,42,0.95)",
                            border: "1px solid rgba(148,163,184,0.18)",
                            borderRadius: "20px",
                            overflow: "hidden",
                            transition: "all 0.25s ease",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: "12px",
                            }}
                          >
                            <h3 style={{ margin: 0 }}>
                              {clip.title}
                            </h3>

                            <span
                              style={{
                                background: "#22c55e",
                                color: "#052e16",
                                padding: "6px 10px",
                                borderRadius: "999px",
                                fontWeight: "900",
                              }}
                            >
                              Score {clip.score}
                            </span>
                          </div>

                          <div style={{ fontWeight: "800", fontSize: "16px", marginTop: "14px", color: "#f8fafc" }}>
                            {clip.title}
                          </div>
                          <p>
                            Niche: {clip.niche}
                          </p>
                          <p>
                            Duration: {clip.duration}s
                          </p>

                          <p style={{ color: "#86efac" }}>
                            {getHashtags(clip).join(" ")}
                          </p>

                          {videoUrl && (
                            <>
                              <div style={{
                                position: "relative",
                                overflow: "hidden",
                                background: "#020617"
                              }}>
                                <video
                                  width="100%"
                                  src={videoUrl}
                                  controls
                                  preload="metadata"
                                  playsInline
                                  style={{
                                    width: "100%",
                                    display: "block",
                                    maxWidth: "340px",
                                    maxHeight: "610px",
                                    margin: "0 auto",
                                    background: "#020617"
                                  }}
                                />

                                <div style={{
                                  position: "absolute",
                                  top: "10px",
                                  right: "10px",
                                  background: "rgba(34,197,94,0.95)",
                                  color: "#022c22",
                                  padding: "6px 10px",
                                  borderRadius: "999px",
                                  fontWeight: "900",
                                  fontSize: "12px"
                                }}>
                                  {clip.score}
                                </div>
                              </div>

                              <a
                                href={videoUrl}
                                download
                                style={{
                                  display: "inline-block",
                                  marginTop: "14px",
                                  background: "linear-gradient(135deg, #22c55e, #38bdf8)",
                                  color: "white",
                                  padding: "12px 16px",
                                  borderRadius: "12px",
                                  textDecoration: "none",
                                  fontWeight: "900",
                                }}
                              >
                                Download Clip
                              </a>
                            </>
                          )}

                          <div
                            style={{
                              marginTop: "16px",
                              background: "rgba(51,65,85,0.8)",
                              padding: "12px",
                              borderRadius: "14px",
                            }}
                          >
                                                        {clip.creator_pack && (
                              <div
                                style={{
                                  marginTop: "14px",
                                  marginBottom: "14px",
                                  padding: "12px",
                                  borderRadius: "14px",
                                  background: "rgba(2,6,23,0.72)",
                                  border: "1px solid rgba(56,189,248,0.22)",
                                }}
                              >
                                <div style={{ fontWeight: "900", marginBottom: "8px", color: "#38bdf8" }}>
                                  📦 Creator Pack
                                </div>
                                <div style={{ fontSize: "13px", color: "#e2e8f0", lineHeight: "1.6" }}>
                                  <div>🎯 Hook: <b>{clip.creator_pack.hook_type}</b></div>
                                  <div>🖼 Thumbnail: <b>{clip.creator_pack.thumbnail_text}</b></div>
                                  <div>📝 Title: <b>{clip.creator_pack.upload_title}</b></div>
                                  <div>📣 CTA: <b>{clip.creator_pack.suggested_cta}</b></div>
                                  {clip.creator_pack.source_credit && (
                                    <div>Source: <b>{clip.creator_pack.source_credit}</b></div>
                                  )}
                                </div>
                                <div style={{ marginTop: "8px", fontSize: "12px", color: "#94a3b8" }}>
                                  {clip.creator_pack.short_description}
                                </div>
                                {Array.isArray(clip.creator_pack.transformation_notes) && clip.creator_pack.transformation_notes.length > 0 && (
                                  <div style={{ marginTop: "8px", fontSize: "12px", color: "#cbd5e1" }}>
                                    {clip.creator_pack.transformation_notes.join(" ")}
                                  </div>
                                )}
                                {clip.creator_pack.generated_description && (
                                  <div style={{ marginTop: "8px", fontSize: "12px", color: "#94a3b8" }}>
                                    {clip.creator_pack.generated_description}
                                  </div>
                                )}
                              </div>
                            )}

                            <div
                              style={{
                                marginTop: "14px",
                                marginBottom: "14px",
                                padding: "12px",
                                borderRadius: "14px",
                                background: "rgba(15,23,42,0.72)",
                                border: "1px solid rgba(148,163,184,0.18)",
                              }}
                            >
                              <div style={{ fontSize: "12px", color: "#94a3b8", fontWeight: "800", marginBottom: "10px" }}>
                                🧠 Teach FluxClip
                              </div>

                              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                                {[
                                  ["good", "great_hook", "👍 Great"],
                                  ["bad", "bad_start", "👎 Bad Start"],
                                  ["bad", "bad_ending", "🛑 Bad Ending"],
                                  ["bad", "boring", "😴 Boring"],
                                  ["bad", "wrong_topic", "🎯 Wrong Topic"],
                                  ["good", "good_context", "✅ Good Context"],
                                ].map(([rating, reason, label]) => {
                                  const fbKey = `${job.id}_${index}`;
                                  const active =
                                    feedbackState[fbKey]?.rating === rating &&
                                    feedbackState[fbKey]?.reason === reason;

                                  return (
                                    <button
                                      key={`${rating}_${reason}`}
                                      onClick={() => submitFeedback(job.id, index, rating, reason)}
                                      style={{
                                        border: "1px solid rgba(148,163,184,0.25)",
                                        background: active
                                          ? "linear-gradient(135deg, #22c55e, #38bdf8)"
                                          : "rgba(2,6,23,0.7)",
                                        color: "white",
                                        borderRadius: "999px",
                                        padding: "8px 10px",
                                        fontSize: "12px",
                                        fontWeight: "800",
                                        cursor: "pointer",
                                      }}
                                    >
                                      {label}
                                    </button>
                                  );
                                })}
                              </div>

                              {feedbackState[`${job.id}_${index}`]?.status === "saved" && (
                                <div style={{ marginTop: "8px", fontSize: "12px", color: "#86efac" }}>
                                  ✅ Feedback saved
                                </div>
                              )}
                            </div>

<strong>Score Breakdown</strong>
                            <pre style={{ overflowX: "auto" }}>
                              {Object.entries(clip.score_breakdown || {})
  .slice(0, 14)
  .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.slice(0, 5).join(", ") : v}`)
  .join("\n")}
                            </pre>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
