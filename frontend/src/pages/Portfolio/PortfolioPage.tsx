import { Navbar } from "../../components/Navbar";
import PortfolioCard from "../../components/PortfolioCard";
import { useAuthContext } from "../../context/AuthContext";
import type { ProjectData } from "../../types/portfolioType";
import "./PortfolioPage.css";

const PROJECTS: ProjectData[] = [
  {
    id: 1,
    title: "Talking with Tito: Learning languages by talking with Tito",
    description: "This is tito",
    image: "/portfolio-assets/titoChatbot.png", // NOTE: images to public/projects/
    tags: ["Python", "NodeJS", "React", "Flask", "MySQL", "Llama.cpp", "spaCy"],
    github: "https://github.com/UCF-ELLE/ELLE-Website-API",
    live: "https://chdr.cs.ucf.edu/elle/home",
  },
  {
    id: 2,
    title: "Rowing Club Management Service",
    description: "",
    image: null,
    tags: ["Python", "FastAPI", "SQLAlchemy", "Alembic", "Docker"],
    github: "https://github.com/PrototypeProto/rowing-club-management-service",
    live: null,
  },
  {
    id: 3,
    title: "Cretastrophe: A 2D drawing puzzle platforming game",
    description: "",
    image: null,
    tags: ["Unity", "C#"],
    github: "https://github.com/JosephS0123/Cretastrophe",
    live: null,
  },
  {
    id: 4,
    title: "My Portfolio",
    description: "",
    image: "/portfolio-assets/portfolioSite.png",
    tags: [
      "Python",
      "PostgreSQL",
      "React",
      "CSS",
      "FastAPI",
      "SQLAlchemy",
      "Alembic",
      "Docker",
    ],
    github: "https://github.com/PrototypeProto/portfolio",
    live: null,
  },
];

export default function PortfolioPage() {
  const { authData } = useAuthContext();
  return (
    <div>
      <Navbar username={authData?.username} />
      <div className="portfolio-page">
        <h1 className="portfolio-heading">Projects</h1>
        <div className="portfolio-grid">
          {PROJECTS.map((project) => (
            <PortfolioCard key={project.id} project={project} />
          ))}
        </div>
      </div>
    </div>
  );
}
