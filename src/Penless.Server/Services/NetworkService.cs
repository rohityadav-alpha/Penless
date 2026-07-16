using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace Penless.Server.Services;

// Figures out which local IP address to show the user.
// The tricky part is that machines often have multiple adapters
// (Wi-Fi, Ethernet, VPN, Hyper-V virtual, etc.) and we want the "real" one.
public sealed class NetworkService
{
    public string GetLocalIpAddress()
    {
        try
        {
            // prefer Wi-Fi or Ethernet adapters that are actually up and have a gateway
            var interfaces = NetworkInterface.GetAllNetworkInterfaces()
                .Where(ni => ni.OperationalStatus == OperationalStatus.Up
                          && ni.NetworkInterfaceType != NetworkInterfaceType.Loopback
                          && ni.NetworkInterfaceType != NetworkInterfaceType.Tunnel)
                .OrderByDescending(ni =>
                    ni.NetworkInterfaceType == NetworkInterfaceType.Wireless80211
                    || ni.NetworkInterfaceType == NetworkInterfaceType.Ethernet);

            foreach (var ni in interfaces)
            {
                var props = ni.GetIPProperties();

                // skip adapters with no default gateway — they're usually not the LAN adapter
                if (props.GatewayAddresses.Count == 0 ||
                    props.GatewayAddresses.All(g => g.Address.Equals(IPAddress.Any)))
                    continue;

                var ipv4 = props.UnicastAddresses
                    .FirstOrDefault(a => a.Address.AddressFamily == AddressFamily.InterNetwork
                                      && !IPAddress.IsLoopback(a.Address));

                if (ipv4 != null)
                    return ipv4.Address.ToString();
            }

            // fallback: the OS picks the right source address when we "connect" to 8.8.8.8
            // (no actual packet is sent — it's just a trick to read LocalEndPoint)
            using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            socket.Connect("8.8.8.8", 80);
            if (socket.LocalEndPoint is IPEndPoint endPoint)
                return endPoint.Address.ToString();
        }
        catch
        {
            // if everything fails, 127.0.0.1 is at least honest
        }

        return "127.0.0.1";
    }

    public bool IsNetworkAvailable()
    {
        return NetworkInterface.GetAllNetworkInterfaces()
            .Any(ni => ni.OperationalStatus == OperationalStatus.Up
                    && ni.NetworkInterfaceType != NetworkInterfaceType.Loopback
                    && ni.NetworkInterfaceType != NetworkInterfaceType.Tunnel);
    }
}
