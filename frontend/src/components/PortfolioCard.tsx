import type { ProjectData } from "../types/portfolioType";
import "./PortfolioCard.css";

interface PortfolioCardProps {
  project: ProjectData;
}

export default function PortfolioCard({ project }: PortfolioCardProps) {
  return (
    <div className="portfolio-card">
      <div className="card-image-wrapper">
        <img
          src={project.image == null ? "/assets/andres.png" : project.image}
          alt={project.title}
          className="card-image"
        />
      </div>

      <div className="card-body">
        <h2 className="card-title">{project.title}</h2>
        <p className="card-description">{project.description}</p>

        <div className="card-tags">
          {project.tags.map((tag) => (
            <span key={tag} className="card-tag">
              {tag}
            </span>
          ))}
        </div>

        <div className="card-links">
          {project.github && (
            <a
              href={project.github}
              target="_blank"
              rel="noopener noreferrer"
              className="card-link"
            >
              GitHub
            </a>
          )}
          {project.live && (
            <a
              href={project.live}
              target="_blank"
              rel="noopener noreferrer"
              className="card-link card-link--live"
            >
              Live
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
