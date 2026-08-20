import NetworkExtension

class VPNPacketTunnelProvider: NEPacketTunnelProvider {
    override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        completionHandler(nil)
    }
}
