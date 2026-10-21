import { Suspense } from "react";
import { Spinner } from "@/components/ui";
import { Automations } from "./automations";

export default function AutomationsPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-24"><Spinner /></div>}>
      <Automations />
    </Suspense>
  );
}
