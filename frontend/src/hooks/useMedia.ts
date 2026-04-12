import { useState, useEffect, useRef } from "react";
import { getMediaList } from "../services/media/mediaService";

export function useMedia() {
  const [filenames, setFilenames] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = async (pageNum: number) => {
    setLoading(true);
    setError(null);

    const { data, ok, error } = await getMediaList(pageNum);

    if (ok && data) {
      setFilenames(data.items);
      setTotalPages(data.pages);
    } else {
      setError(error);
    }

    setLoading(false);
  };

  const _initialFetch = useRef(false);
  useEffect(() => {
    if (page === 1 && !_initialFetch.current) {
      _initialFetch.current = true;
    }
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
