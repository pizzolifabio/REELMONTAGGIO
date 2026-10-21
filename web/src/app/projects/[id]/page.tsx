import { Suspense } from "react";
import { Spinner } from "@/components/ui";
import { Studio } from "./studio";

export default function StudioPage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-24"><Spinner /></div>}>
      <Studio />
    </Suspense>
  );
}
