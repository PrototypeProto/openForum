export const Role = {
  USER: "user",
  VIP: "vip",
  ADMIN: "admin",
} as const;

export type Role = (typeof Role)[keyof typeof Role];

export const isRole = (value: string): value is Role =>
  Object.values(Role).includes(value as Role);