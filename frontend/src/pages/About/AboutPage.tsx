import { Navbar } from "../../components/Navbar"
import "./AboutPage.css"

export default function AboutPage() {
  return (
    <div className="about-page-canvas">
      <Navbar />
      <div className="about-page">

        <h1 className="about-heading">
          This is a social networking site dedicated to my circle of close friends
        </h1>

        <div className="about-section">
          <span>4 types of access</span>
          <ul>
            <li>
              <div>Guests</div>
              <p>People outside my circle that may only view limited sections of this site</p>
            </li>
            <li>
              <div>Members</div>
              <p>Friends of mine with access to use this site</p>
            </li>
            <li>
              <div>VIPs</div>
              <p>Trusted individuals who can handle the extra features responsibly</p>
            </li>
            <li>
              <div>Admin</div>
              <p>AKA 'moi', can do anything I want</p>
            </li>
          </ul>
        </div>

        <div className="about-section">
          <span>Services provided</span>
          <ul>
            <li>
              <div>
                Portfolio
                <span className="about-list-item-badge">Guests+</span>
              </div>
              <p>
                This is a public-facing section of my site that showcases my recent projects
              </p>
            </li>
            <li>
              <div>
                Profile
                <span className="about-list-item-badge">Members+</span>
              </div>
              <p>
                A place to configure account details and how you are portrayed on this site
              </p>
            </li>
            <li>
              <div>
                Forum (The Circle)
                <span className="about-list-item-badge">Members+</span>
              </div>
              <p>
                A forum where we can converse about anything under organized sections
              </p>
            </li>
            <li>
              <div>
                Media
                <span className="about-list-item-badge">Members+</span>
              </div>
              <p>
                A collection of media I have created over the years, often consisting of short moments
                of interest, typically from gaming sessions with friends or a showcase of my skills
              </p>
              <p>
                May eventually allow friends to upload here or to the Forum
              </p>
            </li>
            <li>
              <div>
                Temporary File Storage
                <span className="about-list-item-badge">VIPs+</span>
              </div>
              <p>
                A place where trusted individuals may conveniently upload temporary files to share/move across devices
              </p>
              <p>
                Files uploaded here may have a lifetime of 10m → 24hr before being deleted after the timer expires
              </p>
            </li>
          </ul>
        </div>

      </div>
    </div>
  )
}