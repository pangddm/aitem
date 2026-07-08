body="""
集群：prod-cluster

发现异常：

Namespace: kube-system
Pod: coredns-abc
状态：CrashLoopBackOff

建议：
kubectl describe pod coredns-abc -n kube-system
"""