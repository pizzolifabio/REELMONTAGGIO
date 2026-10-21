import { Suspense } from "react";
import { Spinner } from "@/components/ui";
import { Calendar } from "./calendar";

export default function SchedulePage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-24"><Spinner /></div>}>
      <Calendar />
    </Suspense>
  );
}
