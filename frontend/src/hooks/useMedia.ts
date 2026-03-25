import { useState, useEffect } from "react";
import { getMediaList } from "../services/media/mediaService";

export function useMedia() {
  const [filenames, setFilenames] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(2);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = async (pageNum: number) => {
    setLoading(true);
    setError(null);

    const { data, ok, error } = await getMediaList(pageNum);

    if (ok && data) {
      setFilenames(data); // data is string[] directly
    } else {
      setError(error);
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchPage(page);
  }, [page]);

  const nextPage = () => {
    if (page < totalPages) setPage((p) => p + 1);
  };
  const prevPage = () => {
    if (page > 1) setPage((p) => p - 1);
  };

  return { filenames, page, totalPages, loading, error, nextPage, prevPage };
}
