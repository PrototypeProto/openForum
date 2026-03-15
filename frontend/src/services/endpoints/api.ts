const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const AUTH_URL = `${BASE_URL}/auth`

export const API = {
  auth: {
    signup: `${AUTH_URL}/signup`,
    login: `${AUTH_URL}/login`,
    logout: `${AUTH_URL}/logout`,

    refresh_token: `${AUTH_URL}/refresh_token`,
    promotion_user: (username: string) => `${AUTH_URL}/${username}/promote/user`,
    promotion_vip:  (username: string) => `${AUTH_URL}/${username}/promote/vip`,
    
    all_users: `${AUTH_URL}/all_users`,
    me: `${AUTH_URL}/me`,

  }
}

