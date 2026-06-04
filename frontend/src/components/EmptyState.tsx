import { Link } from "react-router-dom";
import { Microscope } from "lucide-react";

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section
      style={{
        background: "#ffffff",
        border: "1px dashed #e3e8ee",
        borderRadius: "28px",
        padding: "48px 24px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          margin: "0 auto",
          display: "flex",
          height: "56px",
          width: "56px",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "16px",
          background: "#f6f9fc",
          color: "#533afd",
        }}
      >
        <Microscope
          style={{ height: "24px", width: "24px" }}
        />
      </div>
      <h2
        style={{
          color: "#0d253d",
          fontSize: "30px",
          fontWeight: 300,
          marginTop: "20px",
        }}
      >
        {title}
      </h2>
      <p
        style={{
          color: "#64748b",
          margin: "12px auto 0",
          maxWidth: "672px",
          fontSize: "14px",
          lineHeight: "28px",
        }}
      >
        {description}
      </p>
      <Link
        to="/"
        style={{
          marginTop: "24px",
          display: "inline-flex",
          borderRadius: "9999px",
          border: "1px solid #e3e8ee",
          background: "#f6f9fc",
          padding: "8px 16px",
          fontSize: "14px",
          color: "#0d253d",
          transition: "background 150ms",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.background = "#eef2f7";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.background = "#f6f9fc";
        }}
      >
        返回工作台
      </Link>
    </section>
  );
}
