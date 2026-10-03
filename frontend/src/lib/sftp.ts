/** SFTP-Benutzername: `<username>.<erste 8 Zeichen der Instance-UUID>` */
export function sftpUsername(username: string, instanceUuid: string): string {
  return `${username}.${instanceUuid.slice(0, 8)}`;
}
