import "./MediaPage.css";
import { Navbar } from "../../components/Navbar";
import VideoCard from "../../components/VideoCard";
import { useMedia } from "../../hooks/useMedia";

export default function MediaPage() {
  const { filenames, page, totalPages, loading, error, nextPage, prevPage } =
    useMedia();

  return (
    <>
      <Navbar />
      <div className="media-page">
        <h1 className="media-heading">Media</h1>

        {error && <p className="media-error">{error}</p>}

        {loading ? (
          <p className="media-loading">Loading...</p>
        ) : (
          <div className="media-grid">
            {filenames.map((filename) => (
              <VideoCard key={filename} filename={filename} />
            ))}
          </div>
        )}

        <div className="media-pagination">
          <button onClick={prevPage} disabled={page <= 1} className="page-btn">
            Previous
          </button>
          <span className="page-indicator">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={nextPage}
            disabled={page >= totalPages}
            className="page-btn"
          >
            Next
          </button>
        </div>
      </div>
    </>
  );
}
