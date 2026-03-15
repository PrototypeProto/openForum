import { Navbar } from "../../components/Navbar"

export default function LogoutPage() {
    return (
        <div className="logout-page">
            <Navbar username={null}/>
            <h1>Logged out successfully!</h1>

        </div>
    )
}