import { lazy, Suspense } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import Home from "@/pages/Home";

const ReviewPage = lazy(() => import("@/pages/ReviewPage"));
const EvidencePage = lazy(() => import("@/pages/EvidencePage"));
const ReportDetailPage = lazy(() => import("@/pages/ReportDetailPage"));
const ReportComparePage = lazy(() => import("@/pages/ReportComparePage"));
const TrendAnalysisPage = lazy(() => import("@/pages/TrendAnalysisPage"));

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin h-8 w-8 border-2 border-emerald-500 border-t-transparent rounded-full" />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppShell>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/reports/:reportId" element={<ReportDetailPage />} />
            <Route path="/compare" element={<ReportComparePage />} />
            <Route path="/trends" element={<TrendAnalysisPage />} />
          </Routes>
        </Suspense>
      </AppShell>
    </Router>
  );
}
