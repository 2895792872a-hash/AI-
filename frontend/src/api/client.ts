const BASE_URL = "/api";

interface TaskCreateResponse {
  task_id: string;
  status: string;
  created_at: string;
}

interface TaskStatusResponse {
  task_id: string;
  user_task: string;
  status: string;
  stage_progress: string;
  parsed_steps_count: number;
  completed_steps: number;
  failed_steps: number;
  final_summary: string | null;
  extracted_data: Record<string, any> | null;
  error: string | null;
}

export async function createTask(userTask: string): Promise<TaskCreateResponse> {
  const res = await fetch(`${BASE_URL}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_task: userTask }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const res = await fetch(`${BASE_URL}/tasks/${taskId}`);
  if (!res.ok) {
    throw new Error(`Task ${taskId} not found`);
  }
  return res.json();
}
