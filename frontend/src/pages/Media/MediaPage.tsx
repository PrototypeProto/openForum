import { Navbar } from "../../components/Navbar";
import { useAuthContext } from "../../context/AuthContext";

export default function MediaPage() {
    const {getUsernameOrGuest} = useAuthContext()
    return (
        <div>
            <Navbar username={getUsernameOrGuest()}></Navbar>
            <h1>Media pages</h1>
        </div>
    )
}