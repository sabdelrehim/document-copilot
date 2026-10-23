import { BrowserRouter, Route, Routes } from "react-router-dom";

function Shell() {
  return <div className="min-h-dvh bg-background" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<Shell />} />
      </Routes>
    </BrowserRouter>
  );
}
