export interface ProjectData {
  id: number;
  title: string;
  description: string;
  image: string | null;
  tags: string[];
  github: string | null;
  live: string | null;
}