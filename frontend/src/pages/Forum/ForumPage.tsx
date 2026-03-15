import { Navbar } from "../../components/Navbar"
import { useAuthContext } from "../../context/AuthContext";

export default function ForumPage() {
    const {getUsernameOrGuest} = useAuthContext();
    return (
        <><Navbar username={getUsernameOrGuest()}></Navbar><div>
            <h1>Forum</h1>
        </div></>
    )
}