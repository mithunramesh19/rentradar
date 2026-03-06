import type { Metadata } from "next";

import { NotificationsView } from "./notifications-view";

export const metadata: Metadata = {
  title: "Notifications | RentRadar",
  description: "Your listing alerts and updates",
};

export default function NotificationsPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <NotificationsView />
    </div>
  );
}
