import { Navbar } from "../../components/Navbar";
import { useAuthContext } from "../../context/AuthContext";

export default function FileSharePage() {
    const {getUsernameOrGuest} = useAuthContext();

    return (
        <div>
            <Navbar username={getUsernameOrGuest()}></Navbar>
            <h1>24-hour temporary file storage</h1>
        </div>
    )
}