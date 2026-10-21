import { Suspense } from "react";
import { Spinner } from "@/components/ui";
import { Settings } from "./settings";

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-24"><Spinner /></div>}>
      <Settings />
    </Suspense>
  );
}
