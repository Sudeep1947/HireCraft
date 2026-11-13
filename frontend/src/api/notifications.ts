import apiClient from "./client";

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  action_link?: string;
  created_at: string;
  updated_at: string;
}

export const notificationsApi = {
  list: () =>
    apiClient.get<Notification[]>("/notifications").then((r) => r.data),

  getUnreadCount: () =>
    apiClient.get<{ count: number }>("/notifications/unread-count").then((r) => r.data),

  markRead: (id: string) =>
    apiClient.put<Notification>(`/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () =>
    apiClient.put("/notifications/read-all").then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/notifications/${id}`).then((r) => r.data),
};
